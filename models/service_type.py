from sqlalchemy import Column, String, Boolean
import uuid

from database import Base


class ServiceType(Base):
    __tablename__ = "service_types"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    display_name = Column(String, nullable=False)
    category = Column(String, nullable=False)

    is_active = Column(Boolean, nullable=False, default=True, index=True)
