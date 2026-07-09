from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from database import Base
import uuid

class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_type = Column(String, unique=True, index=True, nullable=False) # e.g., "terms", "privacy"
    content = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
