from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class OrderBase(BaseModel):
    type: str
    user_id: int
    driver_id: Optional[int] = None
    pickup_location: Optional[str] = None
    drop_location: Optional[str] = None
    status: Optional[str] = "pending"


class OrderCreate(OrderBase):
    pass


class OrderUpdate(BaseModel):
    type: Optional[str] = None
    driver_id: Optional[int] = None
    pickup_location: Optional[str] = None
    drop_location: Optional[str] = None
    status: Optional[str] = None


class OrderRead(OrderBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True
