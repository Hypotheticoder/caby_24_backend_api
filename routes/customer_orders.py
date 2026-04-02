import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from schemas.customer_order import (
    CustomerOrderCreate,
    CustomerOrderRead,
    CustomerOrderUpdate,
)
import crud.customer_order as crud_customer_order

router = APIRouter(prefix="/customer_orders", tags=["customer_orders"])


@router.post("/create", response_model=CustomerOrderRead)
async def create_customer_order_endpoint(
    order: CustomerOrderCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # 1. Save it to your local Parcel Database first (Your existing code)
    db_order = crud_customer_order.create_customer_order(db, order)

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

    # 3. Fire the payload to the Driver Hub in background so client isn't blocked
    hub_url = f"{os.getenv('DRIVER_HUB_URL')}/dispatch-jobs/create"
    hub_secret = os.getenv("DRIVER_HUB_SECRET")

    async def _post_to_hub(order_id: str, payload: dict, url: str, secret: str):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers={"x-hub-secret": secret}, timeout=5.0)
                response.raise_for_status()
                hub_response_data = response.json()
                # Persist hub_job_id back to DB
                db = SessionLocal()
                try:
                    from crud.customer_order import get_customer_order as _get
                    db_order = db.query(__import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder).filter(
                        __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder.id == order_id
                    ).first()
                    if db_order:
                        db_order.hub_job_id = hub_response_data.get("hub_job_id")
                        db.commit()
                finally:
                    db.close()
                print("SUCCESS! Hub accepted the order (background task).")
            except Exception as e:
                print(f"Background hub post failed: {e}")

    # schedule the background task (non-blocking)
    background_tasks.add_task(_post_to_hub, str(db_order.id), hub_payload, hub_url, hub_secret)

    return db_order


@router.get("/list", response_model=List[CustomerOrderRead])
def list_customer_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_customer_order.get_customer_orders(db, skip, limit)


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


class HubStatusUpdate(BaseModel):
    status: str
    driver_id: str | None = None


@router.post("/{order_id}/hub-webhook", status_code=200)
def receive_hub_update(
    order_id: str,
    payload: HubStatusUpdate,
    db: Session = Depends(get_db),
):
    """
    The Driver Hub will call this endpoint when the driver
    accepts, picks up, or delivers the parcel.
    """
    db_order = crud_customer_order.get_customer_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")

    db_order.status = payload.status
    if payload.driver_id:
        db_order.assigned_driver_id = payload.driver_id

    db.commit()
    db.refresh(db_order)

    print(f"🔄 Parcel Order {order_id} updated to {payload.status} by the Hub!")
    return {"message": "Update received"}
