from datetime import datetime
import uuid
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from database import Base


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    firebase_uid = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=False)

    email = Column(String, unique=True, nullable=True)
    name = Column(String, nullable=True)

    # No enums for now; validate at the API layer if needed.
    role = Column(String, nullable=False, default="driver")

    is_active = Column(Boolean, nullable=False, default=True)

    onboarding_status = Column(String, nullable=False, default="pending_docs")
    live_status = Column(String, nullable=False, default="offline")

    vehicle_type = Column(String, nullable=True)
    vehicle_brand = Column(String, nullable=True)
    vehicle_model = Column(String, nullable=True)
    vehicle_number = Column(String, nullable=True)
    vehicle_color = Column(String, nullable=True)

    profile_photo_url = Column(String, nullable=True)
    driving_license_url = Column(String, nullable=True)
    rc_book_url = Column(String, nullable=True)
    insurance_url = Column(String, nullable=True)
    pan_card_url = Column(String, nullable=True)
    aadhar_card_url = Column(String, nullable=True)
    puc_certificate_url = Column(String, nullable=True)

    rating = Column(Float, nullable=False, default=0.0)
    total_deliveries = Column(Integer, nullable=False, default=0)


