import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import List, Optional
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from datetime import datetime
from schemas.customer_order import (
    CustomerOrderCreate,
    CustomerOrderRead,
    CustomerOrderUpdate,
)
from schemas.payment import PaymentRead
from schemas.customer_order import (
    FareEstimateRequest,
    FareEstimateResponse,
    AllFaresRequest,
    VehicleFareItem,
)
import crud.customer_order as crud_customer_order
from models.earnings_config import EarningsConfig
from dependencies import get_current_user, get_universal_user
from models.user import User
from api.websockets.parcel_ws import parcel_ws_manager
from core.security_logic import PlatformGuard, r


router = APIRouter(prefix="/customer_orders", tags=["customer_orders"])


def is_currently_peak_time(db: Session) -> bool:
    # 🚨 Pointing to the new file instead of earnings_config!
    GlobalTiming = __import__("models.global_timing", fromlist=["GlobalTiming"]).GlobalTiming
    timing = db.query(GlobalTiming).filter(GlobalTiming.id == "master").first()

    if not timing:
        return False

    if timing.manual_peak_override is not None:
        return timing.manual_peak_override

    current_hour = datetime.now().hour

    is_morning = timing.morning_start <= current_hour < timing.morning_end
    is_evening = timing.evening_start <= current_hour < timing.evening_end

    if timing.night_start > timing.night_end:
        is_night = current_hour >= timing.night_start or current_hour < timing.night_end
    else:
        is_night = timing.night_start <= current_hour < timing.night_end

    return is_morning or is_evening or is_night


# --- ROUTE: CALCULATE FARE (Flutter calls this when user selects destination) ---
@router.post("/calculate-fare", response_model=FareEstimateResponse)
def calculate_fare_endpoint(request: FareEstimateRequest, db: Session = Depends(get_db)):
    peak_status = is_currently_peak_time(db)

    config = db.query(EarningsConfig).filter(
        EarningsConfig.service_type == request.service_type.lower(),
        EarningsConfig.is_peak_time == peak_status
    ).first()

    if not config:
        raise HTTPException(status_code=400, detail="Pricing not found for this vehicle.")

    distance_charge = request.distance_km * config.per_km_rate
    raw_fare = config.base_fare + distance_charge
    base_delivery_fee = max(raw_fare, config.minimum_fare)

    live_gst_decimal = float(config.gst_percentage) / 100.0
    gst_amount = round(base_delivery_fee * live_gst_decimal, 2)
    final_total = round(base_delivery_fee + gst_amount, 2)

    return FareEstimateResponse(
        is_peak_time=peak_status,
        base_fare=config.base_fare,
        per_km_rate=config.per_km_rate,
        distance_charge=distance_charge,
        minimum_fare_applied=(base_delivery_fee == config.minimum_fare),
        gst_amount=gst_amount,
        total_fare=final_total,
    )


@router.post("/calculate-all-fares", response_model=List[VehicleFareItem])
def calculate_all_fares_endpoint(request: AllFaresRequest, db: Session = Depends(get_db)):
    peak_status = is_currently_peak_time(db)

    # 🚨 THE MAGIC SLICE & VALIDATION 🚨
    if request.is_parcel:
        # SCENARIO A: User is sending a Parcel
        # 1. Only grab 'parcel_' vehicles.
        # 2. Block any vehicle where the max_weight_kg is less than the user's package weight.
        configs = db.query(EarningsConfig).filter(
            EarningsConfig.is_peak_time == peak_status,
            EarningsConfig.service_type.like("parcel_%"),
            EarningsConfig.max_weight_kg >= request.weight_kg,
            EarningsConfig.max_distance_km >= request.distance_km
        ).all()
    else:
        # SCENARIO B: User is booking a normal Ride
        # Hide all the parcel trucks!
        configs = db.query(EarningsConfig).filter(
            EarningsConfig.is_peak_time == peak_status,
            EarningsConfig.service_type.notlike("parcel_%"),
            EarningsConfig.max_distance_km >= request.distance_km
        ).all()

    if not configs:
        raise HTTPException(status_code=400, detail="No vehicles available for this request.")

    available_rides = []
    for config in configs:
        distance_charge = request.distance_km * config.per_km_rate
        raw_fare = config.base_fare + distance_charge
        base_delivery_fee = max(raw_fare, config.minimum_fare)

        live_gst_decimal = float(config.gst_percentage) / 100.0
        gst_amount = round(base_delivery_fee * live_gst_decimal, 2)
        final_total = round(base_delivery_fee + gst_amount, 2)

        available_rides.append(
            {
                "service_type": config.service_type,
                "base_fare": config.base_fare,
                "per_km_rate": config.per_km_rate,
                "gst_amount": gst_amount,
                "total_fare": final_total,
                "is_peak_time": peak_status,
                "max_weight": config.max_weight_kg, # 👈 Pass it back to Flutter
            }
        )

    return available_rides


@router.post("/create", response_model=CustomerOrderRead)
async def create_customer_order_endpoint(
    order: CustomerOrderCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_universal_user),
    db: Session = Depends(get_db),
):
    user_role = current_user.get("role", "user")
    uid = current_user.get("uid")

    if not uid:
        raise HTTPException(status_code=401, detail="Missing user id in authentication token")
    # 1. Fetch the exact price from admin-configured rules
    peak_status = is_currently_peak_time(db)
    config = (
        db.query(EarningsConfig)
        .filter(
            EarningsConfig.service_type == order.vehicle_type.lower(),
            EarningsConfig.is_peak_time == peak_status,
        )
        .first()
    )

    if not config:
        raise HTTPException(status_code=400, detail="Pricing not found for this vehicle.")

    # 2. Do the exact math securely on the backend
    secure_base_fare = float(config.base_fare)
    secure_distance_charge = float(order.distance_km) * float(config.per_km_rate)
    raw_fare = secure_base_fare + secure_distance_charge
    base_delivery_fee = max(raw_fare, float(config.minimum_fare))

    live_gst_decimal = float(config.gst_percentage) / 100.0
    secure_gst_amount = round(base_delivery_fee * live_gst_decimal, 2)
    secure_total_fare = round(base_delivery_fee + secure_gst_amount, 2)

    # Commission & payout
    # `platform_commission` is treated as a fixed amount (e.g., 10.0 = ₹10).
    secure_platform_commission = min(float(config.platform_commission), base_delivery_fee)
    secure_driver_payout = max(0.0, base_delivery_fee - secure_platform_commission)

    # 🚨 THE PAYMENT SHIELD
    payment_method = (order.payment_method or "").lower()
    if payment_method == "cod":
        desired_status = "PENDING"
    else:
        desired_status = "AWAITING_PAYMENT"

    # 3. Save to DB with backend-forced prices + OTPs
    db_order = crud_customer_order.create_customer_order(
        db,
        order,
        user_id=uid,
        role=user_role,
        secure_base_fare=secure_base_fare,
        secure_distance_charge=secure_distance_charge,
        secure_gst_amount=secure_gst_amount,
        secure_total_fare=secure_total_fare,
        secure_platform_commission=secure_platform_commission,
        secure_driver_payout=secure_driver_payout,
        status_override=desired_status,
    )

    # 1. Import inside the function to prevent circular import crashes
    from routes.drivers import driver_ws_manager

    # 1. We must import FastAPI's JSON encoder to safely convert the DB row
    from fastapi.encoders import jsonable_encoder
    from schemas.customer_order import CustomerOrderRead

    # 2. Convert the entire DB object into a perfect JSON dictionary
    # (This makes it perfectly match what Flutter gets in HTTP requests!)
    perfect_job_dict = jsonable_encoder(CustomerOrderRead.model_validate(db_order))

    # 3. Build the exact structure dispatch_job_service.dart expects
    popup_payload = {
        "event": "NEW_JOB",
        "job": perfect_job_dict,
    }

    background_tasks.add_task(driver_ws_manager.broadcast, popup_payload)

    return db_order


@router.websocket("/ws/track/{order_id}")
async def track_order_websocket(websocket: WebSocket, order_id: str):
    await parcel_ws_manager.connect(websocket, order_id)
    try:
        while True:
            # Keep the connection open; client disconnect triggers WebSocketDisconnect.
            await websocket.receive_text()
    except WebSocketDisconnect:
        parcel_ws_manager.disconnect(websocket, order_id)


@router.get("/list", response_model=List[CustomerOrderRead])
def list_customer_orders(
    skip: int = 0,
    limit: int = 100,  # 🔴 In Swagger UI, change this to 1000 if you have more than 100 rows!
    status_filter: Optional[str] = Query(None, description="Filter by status (e.g., PENDING, ACCEPTED, DELIVERED)"),
    db: Session = Depends(get_db),
):
    # Build a flexible query here so we can filter and order results
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder
    query = db.query(CustomerOrder)

    if status_filter:
        query = query.filter(CustomerOrder.status == status_filter)

    return (
        query.order_by(CustomerOrder.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/me/active", response_model=Optional[CustomerOrderRead])
def get_my_active_order(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder

    active_statuses = [
        "PENDING",
        "ACCEPTED",
        "ARRIVED",
        "PICKED_UP",
        "ON_THE_WAY",
        "EN_ROUTE",
    ]

    active_order = (
        db.query(CustomerOrder)
        .filter(
            CustomerOrder.user_id == current_user.id,
            CustomerOrder.status.in_(active_statuses),
        )
        .order_by(CustomerOrder.created_at.desc())
        .first()
    )

    return active_order


@router.get("/me/history", response_model=List[CustomerOrderRead])
def get_my_order_history(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder

    history = (
        db.query(CustomerOrder)
        .filter(CustomerOrder.user_id == current_user.id)
        .order_by(CustomerOrder.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return history


@router.get("/me/transactions", response_model=List[PaymentRead])
def get_my_transactions(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    Payment = __import__("models.payment", fromlist=["Payment"]).Payment

    transactions = (
        db.query(Payment)
        .filter(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return transactions


@router.get("/{order_id}", response_model=CustomerOrderRead)
def get_customer_order_endpoint(order_id: str, db: Session = Depends(get_db)):
    db_order = crud_customer_order.get_customer_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order


@router.put("/{order_id}", response_model=CustomerOrderRead)
def update_customer_order_endpoint(order_id: str, updates: CustomerOrderUpdate, db: Session = Depends(get_db)):
    db_order = crud_customer_order.get_customer_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    return crud_customer_order.update_customer_order(db, db_order, updates)


@router.delete("/{order_id}", status_code=204)
def delete_customer_order_endpoint(order_id: str, db: Session = Depends(get_db)):
    db_order = crud_customer_order.get_customer_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    crud_customer_order.delete_customer_order(db, db_order)
    return


@router.put("/{order_id}/switch-to-cod")
def switch_order_to_cod(order_id: str, db: Session = Depends(get_db)):
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder
    db_order = db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()

    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")

    if db_order.status != "AWAITING_PAYMENT":
        raise HTTPException(status_code=400, detail="Cannot switch this order to COD")

    db_order.payment_method = "cod"
    db_order.status = "PENDING"
    db.commit()

    return {"message": "Switched to COD successfully", "status": "PENDING"}


@router.websocket("/ws/cancel/{order_id}")
async def cancel_listener_ws(websocket: WebSocket, order_id: str):
    try:
        await parcel_ws_manager.connect(websocket, order_id)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        parcel_ws_manager.disconnect(websocket, order_id)
    except Exception as e:
        print(f"Cancel WS Error: {e}")
        parcel_ws_manager.disconnect(websocket, order_id)
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: str,
    background_tasks: BackgroundTasks,
    user_type: str = Query(..., description="'customer' or 'driver'"),
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder

        db_order = db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()
        if not db_order:
            raise HTTPException(status_code=404, detail="Order not found")

        if db_order.status.upper() in ["ARRIVED", "PICKED_UP", "ON_THE_WAY", "EN_ROUTE", "DELIVERED", "COMPLETED"]:
            raise HTTPException(status_code=403, detail="Driver has arrived or order is in progress. Cannot cancel now.")

        # 1. THE SHIELD: Translate Firebase UID to Database UUID safely
        resolved_user_id = str(user_id)
        if user_type == "driver":
            DriverModel = __import__("models.driver", fromlist=["Driver"]).Driver
            driver = db.query(DriverModel).filter(DriverModel.firebase_uid == user_id).first()
            if not driver and len(user_id) == 36 and "-" in user_id:
                driver = db.query(DriverModel).filter(DriverModel.id == user_id).first()
            if driver:
                resolved_user_id = str(driver.id)

            # Check if they are already banned
            is_banned, msg = PlatformGuard.check_ban(resolved_user_id)
            if is_banned:
                raise HTTPException(status_code=403, detail=msg)

        # 2. ALWAYS FREE THE ORDER FIRST
        if user_type == "driver":
            # Add to Driver's Redis Blacklist (expires in 24h)
            rejected_key = f"rejected:driver:{resolved_user_id}"
            r.sadd(rejected_key, order_id)
            r.expire(rejected_key, 86400)

            # Release job back to map
            db_order.status = "PENDING"
            db_order.assigned_driver_id = None
            db_order.assigned_driver_name = None
            db_order.assigned_driver_phone = None

            # Save the freed order immediately.
            db.commit()

            # 🚨 FIRE THE WEBSOCKET TO THE CUSTOMER!
            background_tasks.add_task(
                parcel_ws_manager.broadcast_to_order,
                order_id,
                {
                    "event": "DRIVER_CANCELLED",
                    "status": "PENDING",
                    "message": "Driver unassigned. Finding a new delivery partner...",
                },
            )
        else:
            # Customer cancelled
            db_order.status = "CANCELLED"
            db.commit()

            background_tasks.add_task(
                parcel_ws_manager.broadcast_to_order,
                order_id,
                {"event": "CUSTOMER_CANCELLED", "status": "CANCELLED"},
            )

            if db_order.assigned_driver_id:
                from routes.drivers import driver_ws_manager

                DriverModel = __import__("models.driver", fromlist=["Driver"]).Driver
                assigned_driver = (
                    db.query(DriverModel)
                    .filter(DriverModel.id == db_order.assigned_driver_id)
                    .first()
                )

                if assigned_driver:
                    background_tasks.add_task(
                        driver_ws_manager.send_personal_message,
                        assigned_driver.firebase_uid,
                        {
                            "event": "CUSTOMER_CANCELLED",
                            "status": "CANCELLED",
                            "order_id": order_id,
                        },
                    )

        # 3. NOW HANDLE THE DRIVER PENALTY
        limit = 2 if user_type == "driver" else 4
        can_cancel = PlatformGuard.attempt_cancellation(user_type, resolved_user_id, limit)

        if not can_cancel:
            if user_type == "driver":
                raise HTTPException(status_code=403, detail="Limit reached! Account suspended for 24 hours.")
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Daily cancellation limit reached. Try again tomorrow.",
                )

        return {"status": "success", "message": "Order cancelled successfully"}

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        return {"status": 500, "message": "Internal server error during cancellation."}


@router.post("/customers/{customer_id}/unsuspend")
def lift_customer_suspension(customer_id: str):
    customer_id_str = str(customer_id)

    ban_key = f"ban:customer:{customer_id_str}"
    new_ban_key = f"banned:customer:{customer_id_str}"
    history_key = f"cancellations:customer:{customer_id_str}"

    # Remove both legacy and new ban keys plus history
    r.delete(ban_key)
    r.delete(new_ban_key)
    r.delete(history_key)

    return {
        "status": "success",
        "message": "Customer suspension lifted. Cancellation strikes reset to 0.",
    }


