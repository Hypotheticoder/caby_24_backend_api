from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    name: str
    phone: Optional[str] = None
    role: str


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None


class UserRead(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True
