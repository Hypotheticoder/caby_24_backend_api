from pydantic import BaseModel, ConfigDict
from typing import Optional, Any, List
from datetime import datetime


class CustomerOrderBase(BaseModel):
    user_id: str
    order_type: str

    pickup_address: str
    pickup_lat: float
    pickup_lng: float
    pickup_contact_name: Optional[str] = None
    pickup_contact_phone: Optional[str] = None

    drop_address: str
    drop_lat: float
    drop_lng: float
    drop_contact_name: Optional[str] = None
    drop_contact_phone: Optional[str] = None

    parcel_type: Optional[str] = None
    parcel_description: Optional[str] = None
    item_count: Optional[int] = None
    weight_kg: Optional[float] = None
    instructions: Optional[str] = None

    vehicle_type: str
    base_fare: float
    distance_km: float
    distance_charge: float
    total_fare: float

    payment_method: str
    payment_status: Optional[str] = "pending"
    is_emergency: Optional[bool] = False
    is_scheduled: Optional[bool] = False
    scheduled_at: Optional[datetime] = None

    status: Optional[str] = "pending"


class CustomerOrderCreate(BaseModel):
    user_id: str
    order_type: str
    vehicle_type: str  # "bike", "cab", etc.
    distance_km: float  # Backend needs this for math!

    pickup_address: str
    pickup_lat: float
    pickup_lng: float
    pickup_contact_name: Optional[str] = None
    pickup_contact_phone: Optional[str] = None

    drop_address: str
    drop_lat: float
    drop_lng: float
    drop_contact_name: Optional[str] = None
    drop_contact_phone: Optional[str] = None

    payment_method: str


class CustomerOrderUpdate(BaseModel):
    order_type: Optional[str] = None
    pickup_address: Optional[str] = None
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    pickup_contact_name: Optional[str] = None
    pickup_contact_phone: Optional[str] = None

    drop_address: Optional[str] = None
    drop_lat: Optional[float] = None
    drop_lng: Optional[float] = None
    drop_contact_name: Optional[str] = None
    drop_contact_phone: Optional[str] = None

    parcel_type: Optional[str] = None
    parcel_description: Optional[str] = None
    item_count: Optional[int] = None
    weight_kg: Optional[float] = None
    instructions: Optional[str] = None

    vehicle_type: Optional[str] = None

    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    is_emergency: Optional[bool] = None
    is_scheduled: Optional[bool] = None
    scheduled_at: Optional[datetime] = None

    status: Optional[str] = None


class CustomerOrderRead(CustomerOrderBase):
    id: str
    created_at: datetime

    driver_payout: Optional[float] = None

    encoded_polyline: Optional[str] = None
    pickup_otp: Optional[str] = None
    drop_otp: Optional[str] = None
    service_details: Optional[Any] = None

    assigned_driver_id: Optional[str] = None
    assigned_driver_name: Optional[str] = None
    assigned_driver_phone: Optional[str] = None

    assigned_driver_lat: Optional[float] = None
    assigned_driver_lng: Optional[float] = None
    last_location_update: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- FARE ESTIMATE SCHEMAS ---

class FareEstimateRequest(BaseModel):
    service_type: str
    distance_km: float

class FareEstimateResponse(BaseModel):
    is_peak_time: bool
    base_fare: float
    per_km_rate: float
    distance_charge: float
    minimum_fare_applied: bool
    total_fare: float    


# --- ALL VEHICLE FARES (Uber/Rapido-style list) ---

# Flutter only needs to send the distance now!
class AllFaresRequest(BaseModel):
    distance_km: float


# The breakdown for a single vehicle in the list
class VehicleFareItem(BaseModel):
    service_type: str
    base_fare: float
    per_km_rate: float
    total_fare: float
    is_peak_time: bool

    model_config = ConfigDict(from_attributes=True)
