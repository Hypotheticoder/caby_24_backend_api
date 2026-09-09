from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from collections import defaultdict
import hashlib
import json
import os
import time
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from core.security_logic import PlatformGuard, r
from core.uploads import ensure_driver_upload_dir, save_upload_file, uploaded_file_url_path
from crud.driver import (
    create_driver,
    delete_driver,
    get_driver,
    get_driver_by_phone,
    get_drivers,
    update_driver,
)
import crud.driver as crud_driver
import crud.customer_order as crud_customer_order
import crud.transaction as crud_transaction
from db import get_db
from dependencies import verify_firebase_token, verify_raw_firebase_token
from schemas.driver import BankDetailPayload, DriverCreate, DriverRead, DriverUpdate
from schemas.customer_order import CustomerOrderRead
from schemas.transaction import (
    AnalyticsDashboard,
    DailyBar,
    PieSlice,
    TransactionRead,
)
from schemas.driver import OTPRequest, OTPVerify, Token

from core.otp import generate_and_save_otp, verify_otp
from core.security import create_access_token, verify_access_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

def get_current_driver(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    token = credentials.credentials
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
        
    phone_number = payload.get("sub")
    if not phone_number:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    driver = crud_driver.get_driver_by_phone(db, phone_number)
    if not driver:
        raise HTTPException(
            status_code=404,
            detail="Driver profile not found.",
        )
    return driver

from api.websockets.parcel_ws import parcel_ws_manager
from routes.customer_orders import is_currently_peak_time
from models.earnings_config import EarningsConfig
from models.transaction import Transaction

router = APIRouter(prefix="/drivers", tags=["drivers"])


class DriverGlobalWSManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, driver_id: str):
        self.active_connections[driver_id] = websocket

    def disconnect(self, driver_id: str):
        if driver_id in self.active_connections:
            del self.active_connections[driver_id]

    async def send_personal_message(self, driver_id: str, message: dict):
        ws = self.active_connections.get(driver_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception as e:
                print(f"Failed to send to driver {driver_id}: {e}")
                self.disconnect(driver_id)

    async def broadcast(self, message: dict):
        dead_connections = []
        for driver_id, ws in self.active_connections.items():
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(driver_id)

        # Clean up anyone who disconnected
        for d_id in dead_connections:
            self.disconnect(d_id)


driver_ws_manager = DriverGlobalWSManager()


@router.post("/login/request-otp")
def request_otp(payload: OTPRequest):
    # Generates a random OTP or a fixed one for the demo account
    otp = generate_and_save_otp(payload.phone_number)
    # TODO: Integrate with SMS gateway here
    print(f"DEBUG: Sent OTP {otp} to {payload.phone_number}")
    return {"message": "OTP sent successfully"}

@router.post("/login/verify-otp", response_model=Token)
def verify_otp_route(payload: OTPVerify, db: Session = Depends(get_db)):
    if not verify_otp(payload.phone_number, payload.otp):
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")
    
    driver = crud_driver.get_driver_by_phone(db, payload.phone_number)
    if not driver:
        # Auto-create profile if doesn't exist
        driver_create = DriverCreate(
            phone_number=payload.phone_number,
            firebase_uid=str(uuid.uuid4())  # Placeholder since we don't use Firebase anymore
        )
        driver = create_driver(db, driver_create)
    
    access_token = create_access_token({"sub": driver.phone_number, "role": "driver"})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/create", response_model=DriverRead, status_code=status.HTTP_201_CREATED)
def create_driver_route(
    payload: DriverCreate,
    db: Session = Depends(get_db),
):
    # Overriding create driver to skip Firebase requirement entirely.
    if hasattr(payload, "model_copy"):
        payload = payload.model_copy(update={"firebase_uid": str(uuid.uuid4())})
    else:
        payload = payload.copy(update={"firebase_uid": str(uuid.uuid4())})

    driver = create_driver(db, payload)
    ensure_driver_upload_dir(driver.name or "driver", driver.firebase_uid)
    return driver


@router.get("/list", response_model=list[DriverRead])
def list_drivers_route(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_drivers(db, skip=skip, limit=limit)


@router.get("/exists")
def driver_phone_exists(
    phone_number: str = Query(..., description="Phone number to check"),
    db: Session = Depends(get_db),
):
    normalized = phone_number.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="phone_number is required")

    driver = get_driver_by_phone(db, normalized)
    if driver:
        return {"exists": True, "driver_id": str(driver.id)}
    return {"exists": False}


@router.get("/me", response_model=DriverRead)
def get_my_driver_profile(current_driver=Depends(get_current_driver)):
    """
    Flutter calls this when the app opens to load their profile.
    It automatically decrypts the token and returns the Driver row.
    """
    return current_driver


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
    current_driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    driver = get_driver(db, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    if driver.id != current_driver.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this profile")

    return update_driver(db, driver, payload)


@router.delete("/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_driver_route(
    driver_id: str,
    current_driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    driver = get_driver(db, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    if driver.id != current_driver.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this profile")

    delete_driver(db, driver)
    return None


@router.post("/{driver_id}/documents")
async def upload_driver_document(
    driver_id: str,
    doc_type: str,
    file: UploadFile = File(...),
    current_driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    driver = get_driver(db, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    if driver.id != current_driver.id:
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






@router.post("/me/logout")
def logout_driver(
    db: Session = Depends(get_db),
    current_driver=Depends(get_current_driver),
):
    try:
        current_driver.live_status = "offline"
        current_driver.fcm_token = None
        db.commit()
        return {
            "status": "success",
            "message": "Driver logged out and safely taken offline.",
        }
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process logout teardown.",
        )


class FCMTokenUpdate(BaseModel):
    fcm_token: str


@router.patch("/me/fcm-token")
def update_fcm_token(
    payload: FCMTokenUpdate,
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    current_driver.fcm_token = payload.fcm_token
    db.commit()
    return {"status": "success", "message": "FCM Token secured."}


@router.get("/me/bank-details")
def get_bank_details(current_driver=Depends(get_current_driver)):
    if not current_driver.bank_account_number:
        return {"has_bank_details": False}

    return {
        "has_bank_details": True,
        "account_name": current_driver.bank_account_name,
        "account_number": current_driver.bank_account_number,
        "ifsc_code": current_driver.bank_ifsc_code,
        "bank_name": current_driver.bank_name,
    }


@router.get("/me/earning-config")
def get_my_earning_config(
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    if not current_driver.vehicle_type:
        raise HTTPException(status_code=400, detail="Vehicle type not set for this driver.")

    sanitized_vehicle = current_driver.vehicle_type.lower()

    config = (
        db.query(EarningsConfig)
        .filter(
            func.lower(EarningsConfig.service_type) == sanitized_vehicle,
            EarningsConfig.is_peak_time == False,
        )
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Pricing configuration not found for {sanitized_vehicle}",
        )

    return {
        "service_type": config.service_type,
        "base_fare": config.base_fare,
        "per_km_rate": config.per_km_rate,
        "minimum_fare": config.minimum_fare,
        "platform_commission": config.platform_commission,
        "gst_percentage": getattr(config, "gst_percentage", 18.0),
    }


@router.put("/me/bank-details")
def update_bank_details(
    payload: BankDetailPayload,
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    crud_driver.update_bank_details(db=db, db_driver=current_driver, payload=payload)
    return {"message": "Bank details saved. Withdrawals locked for 24 hours for security."}


class WithdrawRequestPayload(BaseModel):
    amount: float


@router.post("/me/wallet/settle/initiate")
def initialize_driver_payu(request: WithdrawRequestPayload, current_driver=Depends(get_current_driver)):
    key = os.getenv("PAYU_MERCHANT_KEY", "")
    salt = os.getenv("PAYU_MERCHANT_SALT", "").strip()

    txnid = f"DRV{uuid.uuid4().hex[:10].upper()}"
    
    # 🚨 Force strictly 2 decimal places to fix the PayU 5019 Error
    amount_str = f"{float(request.amount):.2f}"
    
    productinfo = "Platform_Fee_Settlement"
    firstname = current_driver.name.split(" ")[0] if current_driver.name else "Driver"
    email = current_driver.email or "driver@bhukk.com"
    
    # 🚨 Use udf1 for the driver ID so we don't have to touch the database here!
    udf1 = str(current_driver.id)

    # Hash with exactly 10 empty pipes between udf1 and salt
    hash_sequence = f"{key}|{txnid}|{amount_str}|{productinfo}|{firstname}|{email}|{udf1}||||||||||{salt}"
    hash_value = hashlib.sha512(hash_sequence.encode("utf-8")).hexdigest()

    # 🚨 NOTICE: The db.add() is completely gone from here. No more PostgreSQL crashes!

    return {
        "hash": hash_value,
        "txnid": txnid,
        "amount": amount_str,
        "key": key,
        "productinfo": productinfo,
        "firstname": firstname,
        "email": email,
        "udf1": udf1, 
        "surl": "http://192.168.0.222:8000/drivers/me/wallet/settle/callback",
        "furl": "http://192.168.0.222:8000/drivers/me/wallet/settle/callback"
    }


@router.post("/me/wallet/settle/hash")
async def generate_dynamic_payu_hash(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    hash_string = data.get("hash_string") or data.get("hashString", "")
    salt = os.getenv("PAYU_MERCHANT_SALT", "").strip()

    if not salt:
        raise HTTPException(status_code=500, detail="Server misconfiguration: Missing SALT")

    if hash_string:
        hash_sequence = hash_string + salt
        generated_hash = hashlib.sha512(hash_sequence.encode("utf-8")).hexdigest()
        return {"hash": generated_hash}

    raise HTTPException(status_code=400, detail="Missing hash string in request")


@router.post("/me/wallet/settle/callback")
async def driver_payu_callback(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()

    status = form_data.get("status", "")
    txnid = form_data.get("txnid", "")
    posted_hash = form_data.get("hash", "")
    key = form_data.get("key", "")
    productinfo = form_data.get("productinfo", "")
    firstname = form_data.get("firstname", "")
    email = form_data.get("email", "")
    amount = form_data.get("amount", "")

    # 🚨 Get the driver ID back from PayU!
    udf1 = form_data.get("udf1", "") 

    salt = os.getenv("PAYU_MERCHANT_SALT", "").strip()

    # Reverse hash to verify the payment wasn't tampered with
    reverse_hash_seq = f"{salt}|{status}||||||||||{udf1}|{email}|{firstname}|{productinfo}|{amount}|{txnid}|{key}"
    calculated_hash = hashlib.sha512(reverse_hash_seq.encode('utf-8')).hexdigest()

    if calculated_hash == posted_hash and status.lower() == "success":
        # 🚨 Payment is officially safe! NOW we write to the database.
        # We leave order_id=None so the database doesn't crash!
        Transaction = __import__("models.transaction", fromlist=["Transaction"]).Transaction
        db_tx = Transaction(
            driver_id=udf1,
            order_id=None, 
            amount=float(amount),
            transaction_type="settlement",
            payment_mode="payu",
            title="Platform Fees Paid",
            status="completed"
        )
        db.add(db_tx)
        db.commit()
        return RedirectResponse(url=f"bhukkdriver://payment-success?txnid={txnid}", status_code=302)
    else:
        return RedirectResponse(url=f"bhukkdriver://payment-failed?txnid={txnid}", status_code=302)


@router.get("/me/earnings")
def get_dashboard_balances(
    service_type: Optional[str] = Query("all"),
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    Transaction = __import__("models.transaction", fromlist=["Transaction"]).Transaction
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder
    today = date.today()

    def build_query(t_type: str, only_today: bool = False):
        query = db.query(func.sum(Transaction.amount))

        if service_type and service_type.lower() != "all":
            query = query.outerjoin(CustomerOrder, Transaction.order_id == CustomerOrder.id)
            query = query.filter(CustomerOrder.order_type.ilike(f"%{service_type.lower()}%"))

        query = query.filter(
            Transaction.driver_id == current_driver.id,
            func.lower(Transaction.transaction_type) == t_type.lower(),
        )
        if only_today:
            query = query.filter(func.date(Transaction.created_at) == today)
        return query

    online_earn = build_query("earning").scalar() or 0.0
    cash_today = build_query("cash_collected", only_today=True).scalar() or 0.0
    comm_today = build_query("commission", only_today=True).scalar() or 0.0
    total_comm = build_query("commission").scalar() or 0.0

    today_profit = cash_today - comm_today
    net_balance = online_earn - total_comm

    breakdown_query = (
        db.query(
            CustomerOrder.order_type,
            func.sum(
                case(
                    (func.lower(Transaction.transaction_type) == "earning", Transaction.amount),
                    (func.lower(Transaction.transaction_type) == "cash_collected", Transaction.amount),
                    (func.lower(Transaction.transaction_type) == "commission", -Transaction.amount),
                    else_=0,
                )
            ).label("profit"),
        )
        .outerjoin(CustomerOrder, Transaction.order_id == CustomerOrder.id)
        .filter(Transaction.driver_id == current_driver.id)
        .group_by(CustomerOrder.order_type)
        .all()
    )

    ride_total = 0.0
    parcel_total = 0.0
    for row in breakdown_query:
        raw_type = (row.order_type or "").lower()
        profit = float(row.profit or 0.0)
        if "ride" in raw_type:
            ride_total += profit
        elif "parcel" in raw_type:
            parcel_total += profit

    return {
        "today_earnings": today_profit,
        "cash_collected_today": cash_today,
        "amount_owed_to_company": total_comm,
        "net_balance": net_balance,
        "breakdown": {"ride_earnings": ride_total, "parcel_earnings": parcel_total},
    }


@router.get("/me/wallet/statement", response_model=List[TransactionRead])
def get_wallet_statement(
    limit: int = 50,
    service_type: Optional[str] = Query("all"),
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    """
    Returns the raw list of transactions for the Flutter app to display
    in the Earnings Dashboard (like a bank statement).
    """
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder

    query = (
        db.query(Transaction, CustomerOrder)
        .outerjoin(CustomerOrder, Transaction.order_id == CustomerOrder.id)
        .filter(Transaction.driver_id == current_driver.id)
    )

    if service_type and service_type.lower() != "all":
        query = query.filter(CustomerOrder.order_type.ilike(f"%{service_type.lower()}%"))

    results = query.order_by(Transaction.created_at.desc()).limit(limit).all()

    formatted_statement = []

    for tx, order in results:
        formatted_date = tx.created_at.strftime("%b %d, %I:%M %p")

        title = "System Transaction"

        if tx.transaction_type == "EARNING":
            title = f"Payout for {order.order_type.capitalize()}" if order else "Bonus Payout"
        elif tx.transaction_type == "COMMISSION":
            title = "Platform Fee (COD)"
        elif tx.transaction_type == "CASH_COLLECTED":
            title = "Cash Collected from Customer"
        elif tx.transaction_type == "PENALTY":
            title = f"Penalty on Order {str(order.id)[:6]}" if order else "System Penalty"
        elif tx.transaction_type == "SETTLEMENT":
            title = "Paid to Company (Settle Up)"

        formatted_statement.append(
            TransactionRead(
                id=tx.id,
                amount=tx.amount,
                transaction_type=tx.transaction_type,
                payment_mode=tx.payment_mode,
                title=title,
                date=formatted_date,
            )
        )

    return formatted_statement


@router.get("/me/earnings/history", response_model=List[TransactionRead])
def get_earnings_history(
    skip: int = 0,
    limit: int = 10,
    service_type: Optional[str] = Query("all"),
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder

    query = (
        db.query(Transaction, CustomerOrder)
        .outerjoin(CustomerOrder, Transaction.order_id == CustomerOrder.id)
        .filter(Transaction.driver_id == current_driver.id)
    )

    if service_type and service_type.lower() != "all":
        query = query.filter(CustomerOrder.order_type.ilike(f"%{service_type.lower()}%"))

    results = (
        query.order_by(Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    formatted_history = []

    for tx, order in results:
        formatted_date = tx.created_at.strftime("%b %d, %I:%M %p")

        title = "System Transaction"

        if tx.transaction_type == "EARNING":
            title = f"Payout for {order.order_type.capitalize()}" if order else "Bonus Payout"
        elif tx.transaction_type == "COMMISSION":
            title = "Platform Fee (COD)"
        elif tx.transaction_type == "CASH_COLLECTED":
            title = "Cash Collected from Customer"
        elif tx.transaction_type == "PENALTY":
            title = f"Penalty on Order {str(order.id)[:6]}" if order else "System Penalty"
        elif tx.transaction_type == "SETTLEMENT":
            title = "Paid to Company (Settle Up)"

        formatted_history.append(
            TransactionRead(
                id=tx.id,
                amount=tx.amount,
                transaction_type=tx.transaction_type,
                payment_mode=tx.payment_mode,
                title=title,
                date=formatted_date,
            )
        )

    return formatted_history


@router.get("/me/wallet/analytics", response_model=AnalyticsDashboard)
def get_wallet_analytics(
    period: str = Query("weekly", enum=["daily", "weekly", "monthly"]),
    service_type: Optional[str] = Query("all"),
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    Transaction = __import__("models.transaction", fromlist=["Transaction"]).Transaction
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder

    now = datetime.utcnow()
    if period == "daily":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        group_format = "%I %p"
    elif period == "weekly":
        start_date = now - timedelta(days=7)
        group_format = "%a"
    else:
        start_date = now - timedelta(days=30)
        group_format = "%b %d"

    query = (
        db.query(
            func.date(Transaction.created_at).label("date"),
            func.sum(
                case(
                    (func.lower(Transaction.transaction_type) == "earning", Transaction.amount),
                    (func.lower(Transaction.transaction_type) == "cash_collected", Transaction.amount),
                    (func.lower(Transaction.transaction_type) == "commission", -Transaction.amount),
                    else_=0,
                )
            ).label("profit"),
        )
        .outerjoin(CustomerOrder, Transaction.order_id == CustomerOrder.id)
        .filter(
            Transaction.driver_id == current_driver.id,
            Transaction.created_at >= start_date,
        )
    )

    if service_type and service_type.lower() != "all":
        query = query.filter(CustomerOrder.order_type.ilike(f"%{service_type.lower()}%"))

    daily_query = query.group_by(func.date(Transaction.created_at)).all()

    weekly_bars = [
        DailyBar(day=row.date.strftime(group_format), amount=float(row.profit or 0))
        for row in daily_query
    ]

    pie_query = (
        db.query(
            CustomerOrder.order_type,
            func.sum(
                case(
                    (func.lower(Transaction.transaction_type) == "earning", Transaction.amount),
                    (func.lower(Transaction.transaction_type) == "cash_collected", Transaction.amount),
                    (func.lower(Transaction.transaction_type) == "commission", -Transaction.amount),
                    else_=0,
                )
            ).label("total_profit"),
        )
        .outerjoin(CustomerOrder, Transaction.order_id == CustomerOrder.id)
        .filter(
            Transaction.driver_id == current_driver.id,
            Transaction.created_at >= start_date,
        )
    )

    if service_type and service_type.lower() != "all":
        pie_query = pie_query.filter(CustomerOrder.order_type.ilike(f"%{service_type.lower()}%"))

    pie_results = pie_query.group_by(CustomerOrder.order_type).all()

    income_pie = []
    total_profit_sum = sum(float(row.total_profit or 0) for row in pie_results)

    for row in pie_results:
        raw_type = (row.order_type or "other").lower()

        if "parcel" in raw_type:
            display_name = "Parcel"
        elif "ride" in raw_type:
            display_name = "Ride"
        else:
            display_name = raw_type.capitalize()

        amt = float(row.total_profit or 0)

        if amt > 0 and total_profit_sum > 0:
            income_pie.append(
                PieSlice(
                    category=display_name,
                    amount=amt,
                    percentage=round((amt / total_profit_sum) * 100, 1),
                )
            )

    return AnalyticsDashboard(weekly_bars=weekly_bars, income_pie=income_pie)


@router.get("/me/jobs/history", response_model=list[CustomerOrderRead])
def get_job_history(
    skip: int = 0,
    limit: int = 10,
    order_type: Optional[str] = None,
    service_type: Optional[str] = Query(None),
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder

    query = db.query(CustomerOrder).filter(
        CustomerOrder.assigned_driver_id == current_driver.id,
        func.lower(CustomerOrder.status).in_(["completed", "delivered", "cancelled"]),
    )

    type_filter = order_type or service_type
    if type_filter:
        query = query.filter(
            or_(
                CustomerOrder.order_type.ilike(f"%{type_filter}%"),
                CustomerOrder.vehicle_type.ilike(f"%{type_filter}%"),
            )
        )

    return (
        query.order_by(CustomerOrder.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/me/jobs/active", response_model=Optional[CustomerOrderRead])
def get_active_job(
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder

    active_order = (
        db.query(CustomerOrder)
        .filter(
            CustomerOrder.assigned_driver_id == current_driver.id,
            ~func.lower(CustomerOrder.status).in_(["delivered", "cancelled"]),
        )
        .first()
    )

    return active_order


@router.post("/jobs/{order_id}/accept")
def accept_job(
    order_id: str,
    background_tasks: BackgroundTasks,
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    driver_id_str = str(current_driver.id)
    is_banned, msg = PlatformGuard.check_ban(driver_id_str)
    if is_banned:
        raise HTTPException(status_code=403, detail=msg)

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

    background_tasks.add_task(
        driver_ws_manager.broadcast,
        {
            "event": "JOB_TAKEN",
            "order_id": order_id,
        },
    )

    # Forward the driver assignment to Medy Backend
    medy_webhook_url = os.getenv("MEDY_WEBHOOK_URL", "http://127.0.0.1:8000/api/rest/orders/webhook/caby-driver-update")
    medy_payload = {
        "caby_order_id": order_id,
        "driver_id": str(updated_order.assigned_driver_id),
        "driver_name": updated_order.assigned_driver_name,
        "driver_phone": updated_order.assigned_driver_phone,
        "pickup_otp": updated_order.pickup_otp,
        "drop_otp": updated_order.drop_otp,
        "delivery_fee": updated_order.total_fare
    }
    
    def fire_webhook():
        try:
            import requests
            requests.post(medy_webhook_url, json=medy_payload, timeout=3)
        except Exception as e:
            print(f"WEBHOOK ERROR: Failed to forward to Medy: {e}")

    background_tasks.add_task(fire_webhook)

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


class StatusUpdate(BaseModel):
    status: str
    otp: Optional[str] = None


class PaymentStatusUpdate(BaseModel):
    payment_status: str


@router.post("/drivers/{driver_id}/ban")
def manual_driver_ban(
    driver_id: str,
    hours: int = Query(24, description="How many hours to ban?"),
    reason: str = Query(
        "Policy Violation",
        description="Why are they banned? e.g., 'Rude to customer'",
    ),
    # In production, add your admin token verification here!
    # current_admin = Depends(verify_admin_token)
):
    ban_key = f"ban:driver:{driver_id}"

    # 1. Convert hours to seconds for Redis
    total_seconds = hours * 3600

    # 2. Drop the lock! r.setex creates the key, sets the timer, and stores the reason string
    r.setex(ban_key, total_seconds, reason)

    return {
        "status": "success",
        "message": f"Driver locked out for {hours} hours.",
        "reason": reason,
    }


@router.get("/jobs/available", response_model=list[CustomerOrderRead])
def available_jobs(
    driver_lat: float = Query(..., description="Driver's live latitude from Flutter"),
    driver_lng: float = Query(..., description="Driver's live longitude from Flutter"),
    accepts_rides: bool = Query(True, description="Flutter toggle for passenger rides"),
    accepts_parcels: bool = Query(True, description="Flutter toggle for parcel deliveries"),
    accepts_medicine: bool = Query(True, description="Flutter toggle for medicine"),
    skip: int = 0,
    limit: int = 100,
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    driver_id_str = str(current_driver.id)
    is_banned, msg = PlatformGuard.check_ban(driver_id_str)
    if is_banned:
        raise HTTPException(status_code=403, detail=msg)

    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder

    # 1. Grab the raw vehicle type (e.g., "BIKE")
    raw_vehicle_type = current_driver.vehicle_type
    sanitized_vehicle = raw_vehicle_type.lower() if raw_vehicle_type else ""

    # 2. Get the specific Search Radius
    driver_config = (
        db.query(EarningsConfig)
        .filter(
            func.lower(EarningsConfig.service_type) == sanitized_vehicle,
            EarningsConfig.is_peak_time == False,
        )
        .first()
    )
    dynamic_radius = getattr(driver_config, "pickup_radius_km", None) if driver_config else None
    if dynamic_radius is None:
        dynamic_radius = 5.0

    # 3. Build the Allowed Vehicles List
    allowed_vehicle_types = []
    if accepts_rides:
        allowed_vehicle_types.append(sanitized_vehicle)
    if accepts_parcels:
        allowed_vehicle_types.append(f"parcel_{sanitized_vehicle}")
    if accepts_medicine:
        allowed_vehicle_types.append(f"medicine_{sanitized_vehicle}")

    if not allowed_vehicle_types:
        return []

    # 4. The Haversine Formula (Distance Math)
    distance_expr = (
        6371.0 * func.acos(
            func.least(
                1.0,
                func.cos(func.radians(driver_lat))
                * func.cos(func.radians(CustomerOrder.pickup_lat))
                * func.cos(func.radians(CustomerOrder.pickup_lng) - func.radians(driver_lng))
                + func.sin(func.radians(driver_lat))
                * func.sin(func.radians(CustomerOrder.pickup_lat)),
            )
        )
    )

    rejected_key = f"rejected:driver:{driver_id_str}"
    rejected_ids = list(r.smembers(rejected_key) or [])

    # 5. Master Query
    query = db.query(CustomerOrder).filter(
        func.lower(CustomerOrder.status) == "pending",
        CustomerOrder.assigned_driver_id.is_(None),
        CustomerOrder.vehicle_type.in_(allowed_vehicle_types),
        distance_expr <= dynamic_radius,
    )

    if rejected_ids:
        query = query.filter(CustomerOrder.id.notin_(rejected_ids))

    query = query.order_by(distance_expr.asc())

    return query.offset(skip).limit(limit).all()


@router.get("/jobs/available/area-wise")
def available_jobs_area_wise(
    accepts_rides: bool = Query(True, description="Flutter toggle for passenger rides"),
    accepts_parcels: bool = Query(True, description="Flutter toggle for parcel deliveries"),
    accepts_medicine: bool = Query(True, description="Flutter toggle for medicine"),
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    driver_id_str = str(current_driver.id)
    is_banned, msg = PlatformGuard.check_ban(driver_id_str)
    if is_banned:
        raise HTTPException(status_code=403, detail=msg)

    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder

    raw_vehicle_type = current_driver.vehicle_type
    sanitized_vehicle = raw_vehicle_type.lower() if raw_vehicle_type else ""

    allowed_vehicle_types = []
    if accepts_rides:
        allowed_vehicle_types.append(sanitized_vehicle)
    if accepts_parcels:
        allowed_vehicle_types.append(f"parcel_{sanitized_vehicle}")
    if accepts_medicine:
        allowed_vehicle_types.append(f"medicine_{sanitized_vehicle}")

    if not allowed_vehicle_types:
        return {"success": True, "data": []}

    rejected_key = f"rejected:driver:{driver_id_str}"
    rejected_ids = list(r.smembers(rejected_key) or [])

    query = db.query(CustomerOrder).filter(
        func.lower(CustomerOrder.status) == "pending",
        CustomerOrder.assigned_driver_id.is_(None),
        CustomerOrder.vehicle_type.in_(allowed_vehicle_types),
    )

    if rejected_ids:
        query = query.filter(CustomerOrder.id.notin_(rejected_ids))

    available_orders = query.all()

    grouped_orders = defaultdict(list)
    for order in available_orders:
        area_name = getattr(order, "pickup_area", None) or "Unknown Area"
        grouped_orders[area_name].append(
            {
                "id": order.id,
                "order_type": order.order_type,
                "pickup_address": order.pickup_address,
                "drop_address": order.drop_address,
                "total_fare": order.total_fare,
                "distance_km": order.distance_km,
                "estimated_time_mins": order.estimated_time_mins,
                "payment_method": order.payment_method,
            }
        )

    response_data = [
        {
            "area_name": area,
            "order_count": len(orders),
            "orders": orders,
        }
        for area, orders in grouped_orders.items()
    ]

    response_data.sort(key=lambda x: x["order_count"], reverse=True)

    return {"success": True, "data": response_data}


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

    if db_order.assigned_driver_id != current_driver.id:
        raise HTTPException(status_code=403, detail="You do not own this job")

    new_status = payload.status.lower()

    payment_mode = (db_order.payment_method or "online").lower()

    # OTP checks (as usual)
    if new_status == "picked_up":
        if db_order.pickup_otp and payload.otp != db_order.pickup_otp:
            raise HTTPException(status_code=400, detail="Invalid pickup OTP")
    elif new_status == "delivered":
        if db_order.drop_otp and payload.otp != db_order.drop_otp:
            raise HTTPException(status_code=400, detail="Invalid drop-off OTP")

        if payment_mode == "cod" and (db_order.payment_status or "unpaid").lower() != "paid":
            raise HTTPException(
                status_code=403,
                detail=(
                    "Cash collection required! Mark payment as received before completing "
                    "this delivery."
                ),
            )

    # Updated subtraction logic
    if new_status == "delivered" and db_order.status.lower() != "delivered":
        platform_fee = db_order.platform_commission
        if platform_fee is None:
            peak_status = is_currently_peak_time(db)
            config = (
                db.query(EarningsConfig)
                .filter(
                    EarningsConfig.service_type == (db_order.vehicle_type or "").lower(),
                    EarningsConfig.is_peak_time == peak_status,
                )
                .first()
            )
            platform_fee = float(config.platform_commission) if config else 0.0

        driver_earning = float(db_order.total_fare) - float(platform_fee)

        if payment_mode == "online":
            # Record what the driver actually earned after the subtraction
            db.add(
                Transaction(
                    driver_id=current_driver.id,
                    order_id=db_order.id,
                    amount=driver_earning,
                    transaction_type="EARNING",
                    payment_mode="online",
                )
            )
        else:
            # COD flow: Driver has the full cash, but owes you the subtracted amount
            db.add(
                Transaction(
                    driver_id=current_driver.id,
                    order_id=db_order.id,
                    amount=db_order.total_fare,
                    transaction_type="CASH_COLLECTED",
                    payment_mode="cod",
                )
            )

            db.add(
                Transaction(
                    driver_id=current_driver.id,
                    order_id=db_order.id,
                    amount=platform_fee,
                    transaction_type="COMMISSION",
                    payment_mode="cod",
                )
            )

    db_order.status = new_status
    db.commit()

    background_tasks.add_task(
        parcel_ws_manager.broadcast_to_order,
        order_id,
        {"event": "status_update", "status": new_status},
    )
    
    def notify_medy_backend():
        import requests
        medy_webhook_url = os.getenv("MEDY_WEBHOOK_URL", "http://127.0.0.1:8000/api/rest/orders/webhook/caby-driver-update")
        medy_payload = {
            "caby_order_id": str(db_order.id),
            "driver_id": str(current_driver.id),
            "driver_name": current_driver.name,
            "driver_phone": current_driver.phone,
            "status": new_status,
        }
        try:
            requests.post(medy_webhook_url, json=medy_payload, timeout=3)
        except Exception as e:
            print(f"WEBHOOK ERROR: Failed to forward status {new_status} to Medy: {e}")

    background_tasks.add_task(notify_medy_backend)

    return {"message": "status updated", "order_id": order_id, "status": new_status}


@router.put("/jobs/{order_id}/payment")
def update_job_payment_status(
    order_id: str,
    payload: PaymentStatusUpdate,
    current_driver=Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder
    db_order = db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()

    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")

    if db_order.assigned_driver_id != current_driver.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to update this order's payment.",
        )

    db_order.payment_status = payload.payment_status.lower()
    db.commit()

    return {
        "status": "success",
        "message": f"Payment status updated to {payload.payment_status}",
        "order_id": order_id,
        "payment_status": db_order.payment_status,
    }


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

    last_db_save_time = 0.0

    try:
        while True:
            data = await websocket.receive_text()
            try:
                obj = json.loads(data)
                if isinstance(obj, dict) and "lat" in obj and "lng" in obj:
                    await parcel_ws_manager.broadcast_to_order(
                        order_id,
                        {"event": "LOCATION_UPDATE", **obj},
                    )

                    current_time = time.time()
                    if current_time - last_db_save_time > 15:
                        db_order.assigned_driver_lat = float(obj.get("lat"))
                        db_order.assigned_driver_lng = float(obj.get("lng"))
                        db_order.last_location_update = datetime.utcnow()
                        db.commit()

                        last_db_save_time = current_time
                        print(f"✅ DB SAVED: {obj.get('lat')}, {obj.get('lng')}")
            except Exception as e:
                # This will tell you EXACTLY what is wrong.
                print(f"❌ DATABASE UPDATE FAILED: {e}")
                db.rollback()
    except WebSocketDisconnect:
        return


@router.websocket("/ws")
async def driver_global_ws(websocket: WebSocket, token: str = Query(...)):
    await websocket.accept()
    driver_id = None
    try:
        mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user_data = verify_firebase_token(mock_credentials)
        driver_id = user_data.get("uid") or user_data.get("user_id")

        await driver_ws_manager.connect(websocket, driver_id)
        print(f"✅ Global WS Connected for Driver: {driver_id}")

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if driver_id:
            driver_ws_manager.disconnect(driver_id)
        print(f"❌ Global WS Disconnected: {driver_id}")
    except Exception as e:
        print(f"❌ Global WS Error: {e}")
        if driver_id:
            driver_ws_manager.disconnect(driver_id)
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/{driver_id}/unsuspend")
def lift_driver_suspension(driver_id: str):
    driver_id_str = str(driver_id)

    ban_key = f"ban:driver:{driver_id_str}"
    new_ban_key = f"banned:driver:{driver_id_str}"
    history_key = f"cancellations:driver:{driver_id_str}"

    r.delete(ban_key)
    r.delete(new_ban_key)
    r.delete(history_key)

    return {
        "status": "success",
        "message": "Suspension lifted. Cancellation strikes reset to 0.",
    }

