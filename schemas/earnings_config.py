from pydantic import BaseModel
from datetime import datetime

# 1. The base data every config has
class EarningsConfigBase(BaseModel):
    service_type: str
    is_peak_time: bool
    base_fare: float
    per_km_rate: float
    minimum_fare: float
    platform_commission: float

# 2. What the Admin Panel sends when they hit "Save"
class EarningsConfigUpdateRequest(BaseModel):
    base_fare: float
    per_km_rate: float
    minimum_fare: float
    platform_commission: float

# 3. What FastAPI sends back to the Admin Panel to display the table
class EarningsConfigRead(EarningsConfigBase):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True} # This tells Pydantic to read your SQLAlchemy model