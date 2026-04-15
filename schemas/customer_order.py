from pydantic import BaseModel
from typing import Optional, Any
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


class CustomerOrderCreate(CustomerOrderBase):
    pass


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
    base_fare: Optional[float] = None
    distance_km: Optional[float] = None
    distance_charge: Optional[float] = None
    total_fare: Optional[float] = None

    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    is_emergency: Optional[bool] = None
    is_scheduled: Optional[bool] = None
    scheduled_at: Optional[datetime] = None

    status: Optional[str] = None


class CustomerOrderRead(CustomerOrderBase):
    id: str
    created_at: datetime

    encoded_polyline: Optional[str] = None
    pickup_otp: Optional[str] = None
    drop_otp: Optional[str] = None
    service_details: Optional[Any] = None

    hub_job_id: Optional[str] = None
    assigned_driver_id: Optional[str] = None
    assigned_driver_name: Optional[str] = None
    assigned_driver_phone: Optional[str] = None

    model_config = {"from_attributes": True}
