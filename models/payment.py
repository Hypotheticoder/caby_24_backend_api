from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    order_id = Column(String, ForeignKey("customer_orders.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # --- CORE MONEY DETAILS ---
    amount = Column(Float, nullable=False)
    payment_method = Column(String, nullable=False) # e.g., "payu" or "cod"
    
    # Track those split payments your frontend uses
    payment_type = Column(String, nullable=False) # e.g., "full", "first_half", "second_half"

    # --- GATEWAY TRACKING ---
    # This is nullable because COD orders won't have a PayU transaction ID
    transaction_id = Column(String, nullable=True, unique=True, index=True) 
    
    # Track if the money actually cleared
    status = Column(String, default="pending", nullable=False) # "pending", "success", "failed", "refunded"
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # --- RELATIONSHIPS ---
    order = relationship("CustomerOrder", back_populates="payments")
    user = relationship("User", back_populates="payments")
