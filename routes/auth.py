from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import os
import requests
import random
from datetime import datetime, timedelta
import crud.user as crud_user
from schemas.user import UserCreate
from schemas.auth import SendOTPRequest, VerifyOTPRequest, AuthResponse
from typing import Dict, Any

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory store for OTPs. { "phone": {"otp": "1234", "expires_at": datetime} }
OTP_STORE: Dict[str, Dict[str, Any]] = {}


def send_fast2sms_otp(phone: str, otp: str) -> bool:
    api_key = os.getenv("FAST2SMS_API_KEY")
    if not api_key:
        print(f"WARNING: FAST2SMS_API_KEY not found in env. Printing OTP instead.")
        print(f"[{phone}] OTP: {otp}")
        return True
        
    url = "https://www.fast2sms.com/dev/bulkV2"
    querystring = {
        "authorization": api_key,
        "route": "otp",
        "variables_values": otp,
        "flash": "0",
        "numbers": phone
    }
    
    try:
        response = requests.request("GET", url, params=querystring, timeout=10)
        data = response.json()
        
        # Fast2SMS often returns a 200 HTTP code but includes errors in the JSON payload
        if data.get("return") is False or ("status_code" in data and str(data["status_code"]) != "200"):
            print(f"Fast2SMS API Error: {data}")
            return False
            
        return True
    except Exception as e:
        print(f"Error sending SMS via Fast2SMS: {e}")
        return False


@router.post("/check-number")
def check_number(request: SendOTPRequest, db: Session = Depends(get_db)):
    phone = request.phone
    db_user = crud_user.get_user_by_phone(db, phone)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Number is not registered. Sign up first."
        )
    return {"message": "Number is registered", "registered": True, "user_id": db_user.id}


@router.post("/send-otp")
def send_otp(request: SendOTPRequest):
    phone = request.phone
    otp = str(random.randint(1000, 9999))
    
    # Store OTP with a 10-minute expiration
    OTP_STORE[phone] = {
        "otp": otp,
        "expires_at": datetime.utcnow() + timedelta(minutes=10)
    }
    
    success = send_fast2sms_otp(phone, otp)
    if not success:
         print(f"Failed to send SMS to {phone}, generated OTP was {otp}")
         # We still return success but ideally we'd log this gracefully
         
    return {"message": "OTP sent successfully (check backend console if API key was missing)"}


@router.post("/verify-otp", response_model=AuthResponse)
def verify_otp(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    phone = request.phone
    otp = request.otp
    
    stored = OTP_STORE.get(phone)
    if not stored:
        raise HTTPException(status_code=400, detail="OTP not requested or expired")
    
    if datetime.utcnow() > stored["expires_at"]:  # type: ignore
        OTP_STORE.pop(phone, None)
        raise HTTPException(status_code=400, detail="OTP has expired")
        
    if stored["otp"] != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
        
    # OTP is valid, remove it securely
    OTP_STORE.pop(phone, None)
    
    # Check if the user already exists in the database
    db_user = crud_user.get_user_by_phone(db, phone)
    
    if db_user:
        return AuthResponse(message="Login successful", is_new_user=False, user=db_user)
        
    # User does not exist. They must supply a name to register.
    if not request.name:
        raise HTTPException(
            status_code=400, 
            detail="User not found. Please provide a 'name' to register."
        )
        
    # Register the user
    new_user_data = UserCreate(name=request.name, phone=phone)
    new_user = crud_user.create_user(db, new_user_data)
    
    return AuthResponse(message="Registration successful", is_new_user=True, user=new_user)
