from sqlalchemy.orm import Session
from models.payment import Payment
from schemas.payment import PaymentCreate, PaymentUpdate


def get_payment(db: Session, payment_id: str):
    return db.query(Payment).filter(Payment.id == payment_id).first()


def get_payments(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Payment).offset(skip).limit(limit).all()


def create_payment(db: Session, payment: PaymentCreate):
    # support Pydantic v2 (`model_dump`) and v1 (`dict`)
    if hasattr(payment, "model_dump"):
        data = payment.model_dump()
    else:
        data = payment.dict()
    db_payment = Payment(**data)
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment


def update_payment(db: Session, db_payment: Payment, updates: PaymentUpdate):
    if hasattr(updates, "model_dump"):
        data = updates.model_dump(exclude_unset=True)
    else:
        data = updates.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(db_payment, key, value)
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

def get_payment_by_txnid(db: Session, txnid: str):
    db_payment = db.query(Payment).filter(Payment.id == txnid).first()
    if not db_payment:
        db_payment = db.query(Payment).filter(Payment.transaction_id == txnid).first()
    return db_payment

def update_payment_status(db: Session, txnid: str, status: str):
    db_payment = db.query(Payment).filter(Payment.id == txnid).first()
    if not db_payment:
        db_payment = db.query(Payment).filter(Payment.transaction_id == txnid).first()
        
    if db_payment:
        db_payment.status = status
        db.commit()
    return db_payment
