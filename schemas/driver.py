from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class DriverBase(BaseModel):
    # Accept extra fields from the Flutter payload without failing validation.
    model_config = {"extra": "allow", "populate_by_name": True}

    firebase_uid: Optional[str] = None
    phone_number: str
    email: Optional[str] = None
    name: Optional[str] = Field(default=None, alias="full_name")
    role: Optional[str] = "driver"
    is_active: Optional[bool] = True
    onboarding_status: Optional[str] = "pending_docs"
    live_status: Optional[str] = "offline"
    vehicle_type: Optional[str] = None
    vehicle_brand: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_number: Optional[str] = None
    vehicle_color: Optional[str] = None
    profile_photo_url: Optional[str] = None
    driving_license_url: Optional[str] = None
    rc_book_url: Optional[str] = None
    insurance_url: Optional[str] = None
    pan_card_url: Optional[str] = None
    aadhar_card_url: Optional[str] = None
    puc_certificate_url: Optional[str] = None
    rating: Optional[float] = 0.0
    total_deliveries: Optional[int] = 0
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    bank_updated_at: Optional[datetime] = None


class DriverCreate(DriverBase):
    pass


class DriverUpdate(BaseModel):
    firebase_uid: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    onboarding_status: Optional[str] = None
    live_status: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_brand: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_number: Optional[str] = None
    vehicle_color: Optional[str] = None
    profile_photo_url: Optional[str] = None
    driving_license_url: Optional[str] = None
    rc_book_url: Optional[str] = None
    insurance_url: Optional[str] = None
    pan_card_url: Optional[str] = None
    aadhar_card_url: Optional[str] = None
    puc_certificate_url: Optional[str] = None
    rating: Optional[float] = None
    total_deliveries: Optional[int] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    bank_updated_at: Optional[datetime] = None


class DriverRead(DriverBase):
    id: str
    created_at: datetime
    model_config = {"from_attributes": True}


class BankDetailPayload(BaseModel):
    account_name: str
    account_number: str
    ifsc_code: str
    bank_name: str

class OTPRequest(BaseModel):
    phone_number: str

class OTPVerify(BaseModel):
    phone_number: str
    otp: str

class Token(BaseModel):
    access_token: str
    token_type: str
