from sqlalchemy.orm import Session
from models.customer_order import CustomerOrder
from schemas.customer_order import CustomerOrderCreate, CustomerOrderUpdate


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
