from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from database import get_db
from schemas.payment import PaymentCreate, PaymentRead, PaymentUpdate
import crud.payment as crud_payment

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/create", response_model=PaymentRead)
def create_payment_endpoint(payment: PaymentCreate, db: Session = Depends(get_db)):
    return crud_payment.create_payment(db, payment)


@router.get("/list", response_model=List[PaymentRead])
def list_payments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_payment.get_payments(db, skip, limit)


@router.get("/{payment_id}", response_model=PaymentRead)
def get_payment_endpoint(payment_id: str, db: Session = Depends(get_db)):
    db_payment = crud_payment.get_payment(db, payment_id)
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return db_payment


@router.put("/{payment_id}", response_model=PaymentRead)
def update_payment_endpoint(payment_id: str, updates: PaymentUpdate, db: Session = Depends(get_db)):
    db_payment = crud_payment.get_payment(db, payment_id)
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return crud_payment.update_payment(db, db_payment, updates)


@router.delete("/{payment_id}", status_code=204)
def delete_payment_endpoint(payment_id: str, db: Session = Depends(get_db)):
    db_payment = crud_payment.get_payment(db, payment_id)
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    crud_payment.delete_payment(db, db_payment)
    return
