from __future__ import annotations

from datetime import datetime
import json

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from core.uploads import ensure_driver_upload_dir, save_upload_file, uploaded_file_url_path
from crud.driver import (
    create_driver,
    delete_driver,
    get_driver,
    get_driver_by_phone_number,
    list_drivers,
    update_driver,
)
import crud.customer_order as crud_customer_order
from db import get_db
from dependencies import verify_firebase_token
from schemas.driver import DriverCreate, DriverRead, DriverUpdate
from schemas.customer_order import CustomerOrderRead

from routes.customer_orders import parcel_ws_manager

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.post("/create", response_model=DriverRead, status_code=status.HTTP_201_CREATED)
def create_driver_route(
    payload: DriverCreate,
    decoded_token: dict = Depends(verify_firebase_token),
    db: Session = Depends(get_db),
):
    uid = decoded_token.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    # Set firebase_uid from auth token so client doesn't control it
    if hasattr(payload, "model_copy"):
        payload = payload.model_copy(update={"firebase_uid": uid})
    else:
        payload = payload.copy(update={"firebase_uid": uid})

    driver = create_driver(db, payload)
    ensure_driver_upload_dir(driver.name, driver.firebase_uid)
    return driver


@router.get("/list", response_model=list[DriverRead])
def list_drivers_route(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return list_drivers(db, skip=skip, limit=limit)


@router.get("/exists")
def driver_phone_exists(
    phone_number: str = Query(..., description="Phone number to check"),
    db: Session = Depends(get_db),
):
    normalized = phone_number.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="phone_number is required")

    driver = get_driver_by_phone_number(db, normalized)
    return {"exists": driver is not None}


@router.get("/{driver_id}", response_model=DriverRead)
def get_driver_route(driver_id: str, db: Session = Depends(get_db)):
    driver = get_driver(db, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@router.patch("/{driver_id}", response_model=DriverRead)
def patch_driver_route(
    driver_id: str,
    payload: DriverUpdate,
    decoded_token: dict = Depends(verify_firebase_token),
    db: Session = Depends(get_db),
):
    driver = get_driver(db, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    if driver.firebase_uid != decoded_token.get("uid"):
        raise HTTPException(status_code=403, detail="Not authorized to modify this profile")

    return update_driver(db, driver, payload)


@router.delete("/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_driver_route(
    driver_id: str,
    decoded_token: dict = Depends(verify_firebase_token),
    db: Session = Depends(get_db),
):
    driver = get_driver(db, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    if driver.firebase_uid != decoded_token.get("uid"):
        raise HTTPException(status_code=403, detail="Not authorized to modify this profile")

    delete_driver(db, driver)
    return None


@router.post("/{driver_id}/documents")
async def upload_driver_document(
    driver_id: str,
    doc_type: str,
    file: UploadFile = File(...),
    decoded_token: dict = Depends(verify_firebase_token),
    db: Session = Depends(get_db),
):
    driver = get_driver(db, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    if driver.firebase_uid != decoded_token.get("uid"):
        raise HTTPException(status_code=403, detail="Not authorized to modify this profile")

    field_map = {
        "profile_photo": "profile_photo_url",
        "driving_license": "driving_license_url",
        "rc_book": "rc_book_url",
        "insurance": "insurance_url",
        "pan_card": "pan_card_url",
        "aadhar_card": "aadhar_card_url",
        "puc_certificate": "puc_certificate_url",
    }

    field_name = field_map.get(doc_type)
    if field_name is None:
        raise HTTPException(status_code=400, detail="Invalid doc_type")

    dest_dir = ensure_driver_upload_dir(driver.name, driver.firebase_uid)
    saved_path = await save_upload_file(file, dest_dir)
    url_path = uploaded_file_url_path(driver.name, driver.firebase_uid, saved_path.name)

    setattr(driver, field_name, url_path)
    db.add(driver)
    db.commit()
    db.refresh(driver)

    return {"doc_type": doc_type, "url": url_path}


def get_current_driver(decoded_token: dict = Depends(verify_firebase_token), db: Session = Depends(get_db)):
    uid = decoded_token.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    # Find the driver profile for this firebase uid
    DriverModel = __import__("models.driver", fromlist=["Driver"]).Driver
    driver = db.query(DriverModel).filter(DriverModel.firebase_uid == uid).first()
    if not driver:
        raise HTTPException(
            status_code=404,
            detail="Driver profile not found. Call POST /drivers/create first.",
        )
    return driver


class StatusUpdate(BaseModel):
    status: str
    otp: Optional[str] = None


@router.get("/jobs/available", response_model=list[CustomerOrderRead])
def available_jobs(
    skip: int = 0,
    limit: int = 100,
    type_filter: Optional[str] = Query(None, description="Filter by order_type (e.g., ride, parcel)"),
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder
    query = db.query(CustomerOrder).filter(CustomerOrder.status.in_(["PENDING", "pending"]))
    if type_filter:
        query = query.filter(CustomerOrder.order_type == type_filter)

    return (
        query.order_by(CustomerOrder.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("/jobs/{order_id}/accept")
def accept_job(
    order_id: str,
    background_tasks: BackgroundTasks,
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    updated_order = crud_customer_order.assign_driver_to_order(
        db=db,
        order_id=order_id,
        driver_id=current_driver.id,
        driver_name=current_driver.name or "Unknown Driver",
        driver_phone=current_driver.phone_number,
    )
    if not updated_order:
        raise HTTPException(status_code=409, detail="Order is no longer available")

    # Notify customer(s) immediately
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

    return {
        "message": "Job accepted",
        "order_id": order_id,
        "status": updated_order.status,
        "pickup_otp": updated_order.pickup_otp,
        "drop_otp": updated_order.drop_otp,
        "assigned_driver_id": updated_order.assigned_driver_id,
        "assigned_driver_name": updated_order.assigned_driver_name,
        "assigned_driver_phone": updated_order.assigned_driver_phone,
    }


@router.put("/jobs/{order_id}/status")
def update_job_status(
    order_id: str,
    payload: StatusUpdate,
    background_tasks: BackgroundTasks,
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    db_order = crud_customer_order.get_customer_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")

    if db_order.assigned_driver_id and db_order.assigned_driver_id != current_driver.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this job")

    # If marking PICKED_UP, validate pickup OTP if present on order
    if payload.status == "PICKED_UP":
        if db_order.pickup_otp and payload.otp != db_order.pickup_otp:
            raise HTTPException(status_code=400, detail="Invalid pickup OTP")

    # If marking DELIVERED, validate drop-off OTP if present on order
    elif payload.status == "DELIVERED":
        if db_order.drop_otp and payload.otp != db_order.drop_otp:
            raise HTTPException(status_code=400, detail="Invalid drop-off OTP")

    db_order.status = payload.status
    db.commit()

    background_tasks.add_task(
        parcel_ws_manager.broadcast_to_order,
        order_id,
        {"event": "STATUS_UPDATE", "status": payload.status},
    )

    return {"message": "Status updated", "order_id": order_id, "status": payload.status}


@router.websocket("/ws/location/{order_id}")
async def driver_location_ws(
    websocket: WebSocket,
    order_id: str,
    db: Session = Depends(get_db),
):
    await websocket.accept()
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder
    db_order = db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()
    if not db_order:
        print("Order not found, closing socket")
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_text()
            try:
                obj = json.loads(data)
                if isinstance(obj, dict) and "lat" in obj and "lng" in obj:
                    # Update the model instance
                    db_order.assigned_driver_lat = float(obj.get("lat"))
                    db_order.assigned_driver_lng = float(obj.get("lng"))
                    db_order.last_location_update = datetime.utcnow()

                    db.commit()
                    print(f"✅ DB UPDATED: {obj.get('lat')}, {obj.get('lng')}")
            except Exception as e:
                # This will tell you EXACTLY what is wrong.
                print(f"❌ DATABASE UPDATE FAILED: {e}")
                db.rollback()

            if isinstance(obj, dict):
                await parcel_ws_manager.broadcast_to_order(order_id, {"event": "LOCATION_UPDATE", **obj})
    except WebSocketDisconnect:
        return

