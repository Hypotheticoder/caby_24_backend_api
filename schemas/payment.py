from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PaymentBase(BaseModel):
    order_id: str
    user_id: str
    amount: float
    payment_method: str
    payment_type: str
    transaction_id: Optional[str] = None
    status: Optional[str] = "pending"


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    amount: Optional[float] = None
    payment_method: Optional[str] = None
    payment_type: Optional[str] = None
    transaction_id: Optional[str] = None
    status: Optional[str] = None


class PaymentRead(PaymentBase):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}
