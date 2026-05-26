from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from models.carousel_ad import CarouselAd
from schemas.carousel_ad import CarouselAdRead
from core.uploads import ensure_driver_upload_dir, save_upload_file, uploaded_file_url_path


router = APIRouter(prefix="/ads", tags=["ads"])


@router.get("/carousel", response_model=list[CarouselAdRead])
def get_active_ads(db: Session = Depends(get_db)):
    ads = (
        db.query(CarouselAd)
        .filter(CarouselAd.is_active == True)
        .order_by(CarouselAd.display_order.asc())
        .all()
    )
    return ads


@router.post("/create", response_model=CarouselAdRead)
async def create_ad(
    file: UploadFile = File(...),
    title: str = Form(None),
    media_type: str = Form("image"),
    target_url: str = Form(None),
    display_order: int = Form(0),
    db: Session = Depends(get_db),
):
    dest_dir = ensure_driver_upload_dir("ads", "global")
    saved_path = await save_upload_file(file, dest_dir)

    public_url = uploaded_file_url_path("ads", "global", saved_path.name)

    db_ad = CarouselAd(
        title=title,
        media_type=media_type,
        media_url=public_url,
        target_url=target_url,
        display_order=display_order,
    )
    db.add(db_ad)
    db.commit()
    db.refresh(db_ad)

    return db_ad
