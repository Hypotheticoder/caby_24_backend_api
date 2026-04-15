from sqlalchemy.orm import Session
from typing import Optional
import secrets

from models.customer_order import CustomerOrder
from schemas.customer_order import CustomerOrderCreate, CustomerOrderUpdate


def _generate_otp(length: int = 4) -> str:
    # 4-digit numeric OTP by default.
    max_value = 10 ** length
    return str(secrets.randbelow(max_value)).zfill(length)


def get_customer_order(db: Session, order_id: str):
    return db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()


def get_customer_orders(db: Session, skip: int = 0, limit: int = 100):
    return db.query(CustomerOrder).offset(skip).limit(limit).all()


def create_customer_order(db: Session, order: CustomerOrderCreate):
    # support Pydantic v2 (`model_dump`) and v1 (`dict`)
    if hasattr(order, "model_dump"):
        data = order.model_dump()
    else:
        data = order.dict()
    db_order = CustomerOrder(**data)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


def update_customer_order(db: Session, db_order: CustomerOrder, updates: CustomerOrderUpdate):
    if hasattr(updates, "model_dump"):
        data = updates.model_dump(exclude_unset=True)
    else:
        data = updates.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(db_order, key, value)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


def delete_customer_order(db: Session, db_order: CustomerOrder):
    db.delete(db_order)
    db.commit()


def assign_driver_to_order(
    db: Session,
    order_id: str,
    driver_id: str,
    driver_name: Optional[str] = None,
    driver_phone: Optional[str] = None,
) -> CustomerOrder | None:
    """Assign a driver to a customer order and mark it ACCEPTED.

    Returns the updated CustomerOrder or None if not found.
    """
    db_order = db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()
    if not db_order:
        return None

    # Prevent multiple drivers from claiming the same job.
    if (db_order.status or "").upper() != "PENDING":
        return None

    db_order.status = "ACCEPTED"
    db_order.assigned_driver_id = driver_id
    if driver_name is not None:
        db_order.assigned_driver_name = driver_name
    if driver_phone is not None:
        db_order.assigned_driver_phone = driver_phone

    # Generate OTPs on acceptance (monolith flow).
    if not db_order.pickup_otp:
        db_order.pickup_otp = _generate_otp()
    if not db_order.drop_otp:
        db_order.drop_otp = _generate_otp()

    # Ensure pickup/drop OTPs are not identical.
    if db_order.pickup_otp and db_order.drop_otp and db_order.pickup_otp == db_order.drop_otp:
        new_drop_otp = _generate_otp()
        while new_drop_otp == db_order.pickup_otp:
            new_drop_otp = _generate_otp()
        db_order.drop_otp = new_drop_otp

    db.commit()
    db.refresh(db_order)
    return db_order
