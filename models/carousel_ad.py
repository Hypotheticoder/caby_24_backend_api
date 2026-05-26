import uuid
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from database import Base


class CarouselAd(Base):
    __tablename__ = "carousel_ads"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=True)

    media_type = Column(String, nullable=False, default="image")
    media_url = Column(String, nullable=False)
    target_url = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
