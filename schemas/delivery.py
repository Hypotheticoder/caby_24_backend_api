from pydantic import BaseModel
from typing import Optional


class RouteRequest(BaseModel):
    pickup_lat: float
    pickup_lng: float
    drop_lat: float
    drop_lng: float


class RouteResponse(BaseModel):
    status: str
    polyline: Optional[str] = None
    distance_km: float
    estimated_mins: Optional[int] = None
    calculated_fee: float
