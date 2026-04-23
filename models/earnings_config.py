from sqlalchemy import Column, String, Float, Boolean, DateTime
from datetime import datetime
import uuid
from database import Base

class EarningsConfig(Base):
    __tablename__ = "earnings_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    # e.g., 'bike', 'cab', or 'parcel'
    service_type = Column(String, nullable=False, index=True) 
    
    # True = Peak Time (7-11 AM, 5-10 PM), False = Normal Time
    is_peak_time = Column(Boolean, nullable=False, index=True) 

    # --- CABY24 PRICING RULES (The "Menu") ---
    base_fare = Column(Float, nullable=False)
    per_km_rate = Column(Float, nullable=False)
    minimum_fare = Column(Float, nullable=False)
    
    # The fixed commission amount from your document (e.g., ₹10 or ₹20)
    platform_commission = Column(Float, nullable=False) 

    created_at = Column(DateTime, default=datetime.utcnow)