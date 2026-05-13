from sqlalchemy import Column, String, Float, ForeignKey, DateTime
from datetime import datetime
import uuid
from database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    # Unique ID for every single movement of money
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Who does this money belong to?
    driver_id = Column(String, ForeignKey("drivers.id"), nullable=False)

    # What job generated this money? (Nullable because a 'Settlement' payment isn't tied to a specific order)
    order_id = Column(String, ForeignKey("customer_orders.id"), nullable=True)

    # The Bucket: "EARNING" (driver payout), "COMMISSION" (your cut), "CASH_COLLECTED", "SETTLEMENT"
    transaction_type = Column(String, nullable=False)

    # The actual value
    amount = Column(Float, nullable=False)

    # How it was paid: "cod", "online", or "upi"
    payment_mode = Column(String, nullable=False)

    # A short description for UI display
    title = Column(String, nullable=True)

    # When it happened
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="completed", nullable=False)
