from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class TransactionBase(BaseModel):
    transaction_type: str  # "EARNING", "COMMISSION", "CASH_COLLECTED", "PENALTY", "SETTLEMENT"
    amount: float
    payment_mode: str  # "online", "cod", "upi"


class TransactionCreate(TransactionBase):
    driver_id: str
    order_id: Optional[str] = None


class TransactionRead(BaseModel):
    id: str
    amount: float
    transaction_type: str  # "EARNING", "COMMISSION", "CASH_COLLECTED", "PENALTY", "SETTLEMENT"
    payment_mode: str

    # New UI fields for Flutter
    title: str
    date: str

    class Config:
        from_attributes = True  # Tells Pydantic to read SQLAlchemy models


class DailyBar(BaseModel):
    day: str  # e.g., "Mon", "Tue"
    amount: float  # e.g., 450.0


class PieSlice(BaseModel):
    category: str  # e.g., "Rides", "Parcels", "Bonuses"
    amount: float
    percentage: float


class AnalyticsDashboard(BaseModel):
    weekly_bars: List[DailyBar]
    income_pie: List[PieSlice]
