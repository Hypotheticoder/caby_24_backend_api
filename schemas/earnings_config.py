from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# 1. The base data every config has
class EarningsConfigBase(BaseModel):
    service_type: str
    is_peak_time: bool
    base_fare: float
    per_km_rate: float
    minimum_fare: float
    platform_commission: float
    max_weight_kg: Optional[float] = None
    max_distance_km: Optional[float] = None

    gst_percentage: float = 18.0

    # 🚨 Driver pickup search radius (km)
    pickup_radius_km: float = 10.0

# 2. What the Admin Panel sends when they hit "Save"
class EarningsConfigUpdateRequest(BaseModel):
    base_fare: Optional[float] = None
    per_km_rate: Optional[float] = None
    minimum_fare: Optional[float] = None
    platform_commission: Optional[float] = None
    max_weight_kg: Optional[float] = None
    max_distance_km: Optional[float] = None

    gst_percentage: Optional[float] = None

    # 🚨 Allow admins to edit the radius
    pickup_radius_km: Optional[float] = None

# 3. What FastAPI sends back to the Admin Panel to display the table
class EarningsConfigRead(EarningsConfigBase):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True} # This tells Pydantic to read your SQLAlchemy model