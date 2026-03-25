from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    photo_url: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    photo_url: Optional[str] = None


class UserRead(UserBase):
    id: str
    created_at: datetime
    # Pydantic v2: use `model_config` to enable attribute -> model parsing
    model_config = {"from_attributes": True}
