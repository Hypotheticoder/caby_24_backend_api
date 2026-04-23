from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas.earnings_config import EarningsConfigRead, EarningsConfigUpdateRequest, EarningsConfigBase
import crud.earnings_config as crud_earnings_config

router = APIRouter(prefix="/admin/earnings", tags=["Admin Earnings"])

# 1. GET ALL PRICING MENUS (For Flutter Admin Table)
@router.get("/list", response_model=List[EarningsConfigRead])
def get_all_earnings_configs(db: Session = Depends(get_db)):
    configs = crud_earnings_config.list_earnings_configs(db)
    return configs

# 2. UPDATE A SPECIFIC PRICE MENU (When Admin hits Save)
@router.put("/{config_id}", response_model=EarningsConfigRead)
def update_earnings_config(
    config_id: str, 
    updates: EarningsConfigUpdateRequest, 
    db: Session = Depends(get_db)
):
    config = crud_earnings_config.get_earnings_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Earnings configuration not found")

    updated_config = crud_earnings_config.update_earnings_config(db, config, updates)
    return updated_config

# 3. CREATE INITIAL PRICING (Use this in FastAPI /docs to add the PDF data!)
@router.post("/create", response_model=EarningsConfigRead)
def create_initial_config(
    new_config: EarningsConfigBase, 
    db: Session = Depends(get_db)
):
    return crud_earnings_config.create_earnings_config(db, new_config)