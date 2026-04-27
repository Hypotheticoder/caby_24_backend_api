from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.global_timing import GlobalTiming
from schemas.global_timing import GlobalTimingUpdate, GlobalTimingRead

router = APIRouter(prefix="/admin/timing", tags=["Admin Timing"])


@router.get("/master", response_model=GlobalTimingRead)
def get_master_timing(db: Session = Depends(get_db)):
    """Flutter Admin App calls this to load the Settings screen"""
    timing = db.query(GlobalTiming).filter(GlobalTiming.id == "master").first()

    # Auto-create the master row if it doesn't exist yet
    if not timing:
        timing = GlobalTiming(id="master")
        db.add(timing)
        db.commit()
        db.refresh(timing)

    return timing


@router.put("/master", response_model=GlobalTimingRead)
def update_master_timing(payload: GlobalTimingUpdate, db: Session = Depends(get_db)):
    """Flutter Admin App calls this when you hit Save or flip the Master Toggle"""
    timing = db.query(GlobalTiming).filter(GlobalTiming.id == "master").first()

    if not timing:
        timing = GlobalTiming(id="master")
        db.add(timing)

    # Apply all the updates from the Flutter app
    timing.manual_peak_override = payload.manual_peak_override
    timing.morning_start = payload.morning_start
    timing.morning_end = payload.morning_end
    timing.evening_start = payload.evening_start
    timing.evening_end = payload.evening_end
    timing.night_start = payload.night_start
    timing.night_end = payload.night_end

    db.commit()
    db.refresh(timing)

    return timing
