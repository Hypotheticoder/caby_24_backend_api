from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LegalDocumentBase(BaseModel):
    document_type: str
    content: str

class LegalDocumentCreate(LegalDocumentBase):
    pass

class LegalDocumentUpdate(BaseModel):
    content: str

class LegalDocumentResponse(LegalDocumentBase):
    id: str
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        orm_mode = True
