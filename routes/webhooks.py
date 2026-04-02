import os
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.customer_order import CustomerOrder

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# 1. The exact data shape the Driver Hub will send us
class DriverAssignedPayload(BaseModel):
    external_order_id: str  # This matches the CustomerOrder.id!
    driver_id: str
    driver_name: str
    driver_phone: str

@router.post("/driver-assigned")
async def webhook_driver_assigned(
    payload: DriverAssignedPayload,
    x_hub_secret: str = Header(...), # The security check
    db: Session = Depends(get_db)
):
    # Step 1: Verify the bouncer password
    correct_secret = os.getenv("DRIVER_HUB_SECRET", "YOUR_LOCAL_SECRET_FOR_TESTING")
    if x_hub_secret != correct_secret:
        print("SECURITY ALERT: Invalid webhook secret provided.")
        raise HTTPException(status_code=403, detail="Unauthorized Hub")

    # Step 2: Find the original order in our Parcel database
    db_order = db.query(CustomerOrder).filter(
        CustomerOrder.id == payload.external_order_id
    ).first()

    if not db_order:
        print(f"WEBHOOK ERROR: Could not find order {payload.external_order_id}")
        raise HTTPException(status_code=404, detail="Customer Order not found")

    # Step 3: Fill in the empty "Bridge" columns!
    db_order.status = "ASSIGNED"
    db_order.assigned_driver_id = payload.driver_id
    db_order.assigned_driver_name = payload.driver_name
    db_order.assigned_driver_phone = payload.driver_phone

    db.commit()
    db.refresh(db_order)

    return {"status": "success", "message": "Customer DB updated successfully"}
