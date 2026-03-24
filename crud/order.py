from sqlalchemy.orm import Session
from models.order import Order
from schemas.order import OrderCreate, OrderUpdate


def get_order(db: Session, order_id: int):
    return db.query(Order).filter(Order.id == order_id).first()


def get_orders(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Order).offset(skip).limit(limit).all()


def create_order(db: Session, order: OrderCreate):
    db_order = Order(
        type=order.type,
        user_id=order.user_id,
        driver_id=order.driver_id,
        pickup_location=order.pickup_location,
        drop_location=order.drop_location,
        status=order.status,
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


def update_order(db: Session, db_order: Order, updates: OrderUpdate):
    data = updates.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(db_order, key, value)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


def delete_order(db: Session, db_order: Order):
    db.delete(db_order)
    db.commit()
