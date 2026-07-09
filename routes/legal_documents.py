from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.legal_document import LegalDocument
from schemas.legal_document import LegalDocumentCreate, LegalDocumentUpdate, LegalDocumentResponse
from typing import List

router = APIRouter(prefix="/legal-documents", tags=["Legal Documents"])

@router.get("/", response_model=List[LegalDocumentResponse])
def get_all_documents(db: Session = Depends(get_db)):
    return db.query(LegalDocument).all()

@router.get("/{document_type}", response_model=LegalDocumentResponse)
def get_document(document_type: str, db: Session = Depends(get_db)):
    doc = db.query(LegalDocument).filter(LegalDocument.document_type == document_type).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.post("/", response_model=LegalDocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(doc_in: LegalDocumentCreate, db: Session = Depends(get_db)):
    existing = db.query(LegalDocument).filter(LegalDocument.document_type == doc_in.document_type).first()
    if existing:
        raise HTTPException(status_code=400, detail="Document type already exists")
    
    # Use model_dump for Pydantic V2 or dict for V1
    doc_data = doc_in.model_dump() if hasattr(doc_in, 'model_dump') else doc_in.dict()
    new_doc = LegalDocument(**doc_data)
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return new_doc

@router.put("/{document_type}", response_model=LegalDocumentResponse)
def update_document(document_type: str, doc_in: LegalDocumentUpdate, db: Session = Depends(get_db)):
    doc = db.query(LegalDocument).filter(LegalDocument.document_type == document_type).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc.content = doc_in.content
    db.commit()
    db.refresh(doc)
    return doc
