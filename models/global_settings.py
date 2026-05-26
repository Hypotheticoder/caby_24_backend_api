from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from database import Base


class GlobalSetting(Base):
    __tablename__ = "global_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
