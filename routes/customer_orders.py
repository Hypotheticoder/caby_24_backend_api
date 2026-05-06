import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, WebSocket, WebSocketDisconnect
from typing import List, Optional
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from datetime import datetime
from schemas.customer_order import (
    CustomerOrderCreate,
    CustomerOrderRead,
    CustomerOrderUpdate,
)
from schemas.customer_order import (
    FareEstimateRequest,
    FareEstimateResponse,
    AllFaresRequest,
    VehicleFareItem,
)
import crud.customer_order as crud_customer_order
from models.earnings_config import EarningsConfig
from dependencies import get_current_user
from models.user import User


# Real-time tracking manager for customers watching an order
class ParcelTrackingManager:
    def __init__(self):
        # Maps order_id -> list of active WebSocket connections
        self.active_rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, order_id: str):
        await websocket.accept()
        if order_id not in self.active_rooms:
            self.active_rooms[order_id] = []
        self.active_rooms[order_id].append(websocket)

    def disconnect(self, websocket: WebSocket, order_id: str):
        if order_id in self.active_rooms and websocket in self.active_rooms[order_id]:
            self.active_rooms[order_id].remove(websocket)

    async def broadcast_to_order(self, order_id: str, message: dict):
        if order_id in self.active_rooms:
            for connection in list(self.active_rooms[order_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(connection, order_id)


parcel_ws_manager = ParcelTrackingManager()


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

    # Calculate exact math
    distance_charge = request.distance_km * config.per_km_rate
    raw_fare = config.base_fare + distance_charge
    final_fare = max(raw_fare, config.minimum_fare)

    return FareEstimateResponse(
        is_peak_time=peak_status,
        base_fare=config.base_fare,
        per_km_rate=config.per_km_rate,
        distance_charge=distance_charge,
        minimum_fare_applied=(final_fare == config.minimum_fare),
        total_fare=final_fare
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
        actual_total = max(raw_fare, config.minimum_fare)

        available_rides.append(
            {
                "service_type": config.service_type,
                "base_fare": config.base_fare,
                "per_km_rate": config.per_km_rate,
                "total_fare": actual_total,
                "is_peak_time": peak_status,
                "max_weight": config.max_weight_kg, # 👈 Pass it back to Flutter
            }
        )

    return available_rides


@router.post("/create", response_model=CustomerOrderRead)
async def create_customer_order_endpoint(
    order: CustomerOrderCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    secure_total_fare = max(raw_fare, float(config.minimum_fare))

    # Commission & payout
    # `platform_commission` is treated as a fixed amount (e.g., 10.0 = ₹10).
    secure_platform_commission = min(float(config.platform_commission), secure_total_fare)
    secure_driver_payout = max(0.0, secure_total_fare - secure_platform_commission)

    # 3. Save to DB with backend-forced prices + OTPs
    db_order = crud_customer_order.create_customer_order(
        db,
        order,
        user_id=current_user.id,
        secure_base_fare=secure_base_fare,
        secure_distance_charge=secure_distance_charge,
        secure_total_fare=secure_total_fare,
        secure_platform_commission=secure_platform_commission,
        secure_driver_payout=secure_driver_payout,
    )

    # 2. Package the data for the Driver Hub
    # Notice how we bundle your specific parcel details into the 'requirements' dictionary!
    hub_payload = {
        "source_app": "PARCEL_APP",
        "external_order_id": str(db_order.id), # The magic bridge ID
        
        "pickup_address": db_order.pickup_address,
        "pickup_lat": db_order.pickup_lat,
        "pickup_lng": db_order.pickup_lng,
        "drop_address": db_order.drop_address,
        "drop_lat": db_order.drop_lat,
        "drop_lng": db_order.drop_lng,
        "encoded_polyline": db_order.encoded_polyline,
        
        "delivery_fee": db_order.distance_charge, # What you pay the driver
        "requirements": {
            "order_type": db_order.order_type,
            "parcel_type": db_order.parcel_type,
            "weight_kg": db_order.weight_kg,
            "item_count": db_order.item_count,
            "instructions": db_order.instructions
        }
    }

    # In the monolith we no longer post to an external Driver Hub.
    # The driver app will query `/drivers/jobs/available` and accept jobs directly.

    return db_order


@router.websocket("/ws/track/{order_id}")
async def track_order_websocket(websocket: WebSocket, order_id: str):
    await parcel_ws_manager.connect(websocket, order_id)
    try:
        while True:
            # 1. Listen for incoming JSON from the Driver App
            data = await websocket.receive_text()
            parsed_data = json.loads(data)

            # 2. Instantly bounce that JSON to the Customer App!
            await parcel_ws_manager.broadcast_to_order(order_id, parsed_data)
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


from pydantic import BaseModel
from typing import Optional

# 1. Upgraded Webhook Payload (Now accepts name and phone!)
class HubStatusUpdate(BaseModel):
    status: str
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None

# 2. Upgraded Webhook Route
@router.post("/{order_id}/hub-webhook", status_code=200)
def receive_hub_update(
    order_id: str,
    payload: HubStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    The Driver Hub will call this endpoint when the driver
    accepts, picks up, or delivers the parcel.
    """
    # Check if the Hub sent an "ACCEPTED" status with driver details
    if payload.status == "ACCEPTED" and payload.driver_id:

        # Call CRUD helper to assign the driver
        updated_order = crud_customer_order.assign_driver_to_order(
            db=db,
            order_id=order_id,
            driver_id=payload.driver_id,
            driver_name=payload.driver_name or "Unknown Driver",
            driver_phone=payload.driver_phone or "N/A",
        )

        if not updated_order:
            raise HTTPException(status_code=404, detail="Order not found in Parcel DB")

        # Broadcast to any connected customers watching this order (non-blocking)
        background_tasks.add_task(
            parcel_ws_manager.broadcast_to_order,
            order_id,
            {
                "event": "DRIVER_ASSIGNED",
                "assigned_driver_name": updated_order.assigned_driver_name,
                "assigned_driver_phone": updated_order.assigned_driver_phone,
                "pickup_otp": updated_order.pickup_otp,
                    "drop_otp": updated_order.drop_otp,
                "status": "ACCEPTED",
            },
        )

        print(f"✅ Parcel Order {order_id} was just accepted by {payload.driver_name}!")

    else:
        # If it's just a standard status update (like "DELIVERED"), just update the status
        db_order = crud_customer_order.get_customer_order(db, order_id)
        if not db_order:
            raise HTTPException(status_code=404, detail="Order not found")

        db_order.status = payload.status
        db.commit()

        # Notify watchers of status change
        background_tasks.add_task(
            parcel_ws_manager.broadcast_to_order,
            order_id,
            {"event": "STATUS_UPDATE", "status": payload.status},
        )

    return {"message": "Webhook successfully saved to Parcel Database"}
