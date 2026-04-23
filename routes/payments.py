from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from typing import List
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import hashlib
from database import get_db
from schemas.payment import PaymentCreate, PaymentRead, PaymentUpdate
import crud.payment as crud_payment
from models.customer_order import CustomerOrder
from models.payment import Payment

router = APIRouter(prefix="/payments", tags=["payments"])

class InitPayURequest(BaseModel):
    order_id: str


@router.post("/init-payu")
def initialize_payu(request: InitPayURequest, db: Session = Depends(get_db)):
    order = db.query(CustomerOrder).filter(CustomerOrder.id == request.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    key = os.getenv("PAYU_MERCHANT_KEY", "")
    salt = os.getenv("PAYU_MERCHANT_SALT", "")

    txnid = f"TXN_{order.id[:10].upper()}"
    amount = float(order.total_fare)
    productinfo = order.id
    firstname = order.user_id
    email = "customer@bhukk.com"

    hash_sequence = f"{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|||||||||||{salt}"
    hash_value = hashlib.sha512(hash_sequence.encode("utf-8")).hexdigest()

    # Create a pending payment record if one doesn't exist for this txnid.
    existing = db.query(Payment).filter(Payment.transaction_id == txnid).first()
    if not existing:
        db_payment = Payment(
            order_id=order.id,
            user_id=order.user_id,
            amount=amount,
            payment_method="payu",
            payment_type="full",
            transaction_id=txnid,
            status="pending",
        )
        db.add(db_payment)
        db.commit()

    return {
        "hash": hash_value,
        "txnid": txnid,
        "amount": amount,
        "key": key,
        "productinfo": productinfo,
        "firstname": firstname,
        "email": email,
    }

@router.post("/callback")
async def payu_callback(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    
    status = form_data.get("status", "")
    firstname = form_data.get("firstname", "")
    amount = form_data.get("amount", "")
    txnid = form_data.get("txnid", "")
    posted_hash = form_data.get("hash", "")
    key = form_data.get("key", "")
    productinfo = form_data.get("productinfo", "")
    email = form_data.get("email", "")
    
    udf1 = form_data.get("udf1", "")
    udf2 = form_data.get("udf2", "")
    udf3 = form_data.get("udf3", "")
    udf4 = form_data.get("udf4", "")
    udf5 = form_data.get("udf5", "")
    additional_charges = form_data.get("additionalCharges")
    
    salt = os.getenv("PAYU_MERCHANT_SALT", "")
    
    if additional_charges:
        reverse_hash_seq = f"{additional_charges}|{salt}|{status}||||||{udf5}|{udf4}|{udf3}|{udf2}|{udf1}|{email}|{firstname}|{productinfo}|{amount}|{txnid}|{key}"
    else:
        reverse_hash_seq = f"{salt}|{status}||||||{udf5}|{udf4}|{udf3}|{udf2}|{udf1}|{email}|{firstname}|{productinfo}|{amount}|{txnid}|{key}"
        
    calculated_hash = hashlib.sha512(reverse_hash_seq.encode('utf-8')).hexdigest()
    
    if calculated_hash == posted_hash:
        print(f"Verified successful payment webhook for txnid: {txnid}")
        
        # 1. Fetch the original order from your DB
        original_order = crud_payment.get_payment_by_txnid(db, txnid)
        
        # 2. Check the amount! (Convert both to float to be safe)
        if original_order and float(original_order.amount) == float(amount):
            # 🟢 ALL GOOD! Update DB
            crud_payment.update_payment_status(db, txnid=txnid, status=status)
        else:
            # 🔴 FRAUD DETECTED!
            print("Amount mismatch! User tampered with the price.")
            crud_payment.update_payment_status(db, txnid=txnid, status="FAILED_AMOUNT_MISMATCH")
            status = "failed"
            
    else:
        print(f"Hash mismatch for txnid: {txnid} - POTENTIAL FRAUD")
        # 🔴 Mark as failed/tampered in DB
        crud_payment.update_payment_status(db, txnid=txnid, status="FAILED_TAMPERED")
        status = "failed"
        
    if status.lower() == "success":
        return RedirectResponse(url=f"bhukk://payment-success?txnid={txnid}")
    else:
        return RedirectResponse(url=f"bhukk://payment-failed?txnid={txnid}")


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
