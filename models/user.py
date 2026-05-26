from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime
from database import Base
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    firebase_uid = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True) 
    phone = Column(String, nullable=False, unique=True)
    photo_url = Column(String, nullable=True) 
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    orders = relationship(
        "CustomerOrder",
        back_populates="user",
        primaryjoin="User.id==CustomerOrder.user_id",
        foreign_keys="CustomerOrder.user_id",
    )
    payments = relationship("Payment", back_populates="user")
