from sqlalchemy import func
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


def create_customer_order(
    db: Session,
    order: CustomerOrderCreate,
    user_id: str,
    role: str,
    secure_base_fare: float,
    secure_distance_charge: float,
    secure_gst_amount: float,
    secure_total_fare: float,
    secure_platform_commission: float,
    secure_driver_payout: float,
    status_override: str | None = None,
):
    # Convert Pydantic model to dictionary
    if hasattr(order, "model_dump"):
        data = order.model_dump()
    else:
        data = order.dict()

    data["user_id"] = user_id

    # Fall back to user's registered name and phone if contact fields are empty
    user_name = "Customer"
    user_phone = ""

    if role == "medicine_shop":
        from models.pharma_shop_user import PharmaShopUser

        shop = db.query(PharmaShopUser).filter(PharmaShopUser.shop_id == user_id).first()
        if shop:
            user_name = shop.shop_name
            user_phone = shop.shop_phone_no
    elif role == "system":
        user_name = "Partner App"
        user_phone = "N/A"
    else:
        from models.user import User

        db_user = db.query(User).filter(User.id == user_id).first()
        if db_user:
            user_name = db_user.name
            user_phone = db_user.phone

    if not data.get("pickup_contact_name") or str(data.get("pickup_contact_name")).strip() == "":
        data["pickup_contact_name"] = user_name
    if not data.get("pickup_contact_phone") or str(data.get("pickup_contact_phone")).strip() == "":
        data["pickup_contact_phone"] = user_phone
    if not data.get("drop_contact_name") or str(data.get("drop_contact_name")).strip() == "":
        data["drop_contact_name"] = user_name
    if not data.get("drop_contact_phone") or str(data.get("drop_contact_phone")).strip() == "":
        data["drop_contact_phone"] = user_phone

    # 🔒 THE SECURITY LOCK: Force the backend prices
    data["base_fare"] = secure_base_fare
    data["distance_charge"] = secure_distance_charge
    data["gst_amount"] = secure_gst_amount
    data["total_fare"] = secure_total_fare
    data["platform_commission"] = secure_platform_commission
    data["driver_payout"] = secure_driver_payout
    data["status"] = status_override or "pending"
    data["payment_status"] = "pending"

    # 🔐 Generate OTPs
    data["pickup_otp"] = _generate_otp()
    data["drop_otp"] = _generate_otp()

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
    pickup_otp = _generate_otp()
    drop_otp = _generate_otp()
    while drop_otp == pickup_otp:
        drop_otp = _generate_otp()

    update_values = {
        "assigned_driver_id": driver_id,
        "status": "ACCEPTED",
        "pickup_otp": func.coalesce(CustomerOrder.pickup_otp, pickup_otp),
        "drop_otp": func.coalesce(CustomerOrder.drop_otp, drop_otp),
    }
    if driver_name is not None:
        update_values["assigned_driver_name"] = driver_name
    if driver_phone is not None:
        update_values["assigned_driver_phone"] = driver_phone

    result = (
        db.query(CustomerOrder)
        .filter(
            CustomerOrder.id == order_id,
            CustomerOrder.assigned_driver_id.is_(None),
            func.lower(CustomerOrder.status) == "pending",
        )
        .update(update_values, synchronize_session=False)
    )

    db.commit()

    if result == 0:
        return None

    return db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()
