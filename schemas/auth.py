from pydantic import BaseModel
from typing import Optional
from schemas.user import UserRead


class SendOTPRequest(BaseModel):
    phone: str


class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str
    name: Optional[str] = None


class AuthResponse(BaseModel):
    message: str
    is_new_user: bool
    user: Optional[UserRead] = None
