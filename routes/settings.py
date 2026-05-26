from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas.global_settings import GlobalSettingCreate, GlobalSettingRead
import crud.global_settings as crud_global_settings


router = APIRouter(prefix="/settings", tags=["Global Settings"])


@router.get("/{key}", response_model=GlobalSettingRead)
def get_setting(key: str, db: Session = Depends(get_db)):
    setting = crud_global_settings.get_setting(db, key)
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found.")
    return setting


@router.get("/list/all", response_model=List[GlobalSettingRead])
def list_all_settings(db: Session = Depends(get_db)):
    return crud_global_settings.get_all_settings(db)


@router.post("/upsert", response_model=GlobalSettingRead)
def upsert_setting(payload: GlobalSettingCreate, db: Session = Depends(get_db)):
    return crud_global_settings.upsert_setting(db, payload)


@router.delete("/{key}")
def delete_setting(key: str, db: Session = Depends(get_db)):
    success = crud_global_settings.delete_setting(db, key)
    if not success:
        raise HTTPException(status_code=404, detail="Setting not found.")
    return {"status": "success", "message": f"Setting '{key}' successfully deleted."}
