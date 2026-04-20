import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from database import Base


class CustomerOrder(Base):
    __tablename__ = "customer_orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # 1. Order Type
    order_type = Column(String, nullable=False)  # "parcel" or "ride"

    # 2. Location Data
    pickup_address = Column(String, nullable=False)
    pickup_lat = Column(Float, nullable=False)
    pickup_lng = Column(Float, nullable=False)
    pickup_contact_name = Column(String, nullable=True)
    pickup_contact_phone = Column(String, nullable=True)

    drop_address = Column(String, nullable=False)
    drop_lat = Column(Float, nullable=False)
    drop_lng = Column(Float, nullable=False)
    drop_contact_name = Column(String, nullable=True)
    drop_contact_phone = Column(String, nullable=True)

    # 3. Parcel Specifics
    parcel_type = Column(String, nullable=True)
    parcel_description = Column(String, nullable=True)
    item_count = Column(Integer, nullable=True)
    weight_kg = Column(Float, nullable=True)
    instructions = Column(String, nullable=True)

    # 4. Pricing & Logistics
    vehicle_type = Column(String, nullable=False)
    base_fare = Column(Float, nullable=False)
    distance_km = Column(Float, nullable=False)
    distance_charge = Column(Float, nullable=False)
    total_fare = Column(Float, nullable=False)

    # 5. Payment & Status
    payment_method = Column(String, nullable=False)  # "online" or "cod"
    payment_status = Column(String, default="pending")
    is_emergency = Column(Boolean, default=False)
    is_scheduled = Column(Boolean, default=False)
    scheduled_at = Column(DateTime, nullable=True)

    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    encoded_polyline = Column(String, nullable=True)
    
    pickup_otp = Column(String, nullable=True)
    drop_otp = Column(String, nullable=True)  

    service_details = Column(JSONB, nullable=True) 

    # ---------------------------------------------------------
    # DRIVER ASSIGNMENT (Order is the job)
    # ---------------------------------------------------------
    assigned_driver_id = Column(String, ForeignKey("drivers.id"), nullable=True)
    assigned_driver_name = Column(String, nullable=True)
    assigned_driver_phone = Column(String, nullable=True)

    # Last known driver position for this order
    assigned_driver_lat = Column(Float, nullable=True)
    assigned_driver_lng = Column(Float, nullable=True)
    last_location_update = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="orders")
    driver = relationship("Driver", back_populates="assigned_orders")
    payments = relationship("Payment", back_populates="order")
