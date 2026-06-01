from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AdminLogin(BaseModel):
    email: str
    password: str


class AdminCreate(BaseModel):
    name: str
    email: str
    password: str
    role: Optional[str] = "superadmin"


class AdminRead(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str
