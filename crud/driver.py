from sqlalchemy.orm import Session
from models.driver import Driver
from schemas.driver import DriverCreate, DriverUpdate


def get_drivers(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Driver).offset(skip).limit(limit).all()


def get_driver(db: Session, driver_id: str):
    return db.query(Driver).filter(Driver.id == driver_id).first()


def get_driver_by_phone(db: Session, phone: str):
    return db.query(Driver).filter(Driver.phone_number == phone).first()


def get_driver_by_firebase_uid(db: Session, firebase_uid: str):
    return db.query(Driver).filter(Driver.firebase_uid == firebase_uid).first()




def create_driver(db: Session, driver: DriverCreate):
    db_driver = Driver(
        firebase_uid=driver.firebase_uid,
        phone_number=driver.phone_number,
        email=driver.email,
        name=driver.name,
        role=driver.role or "driver",
        is_active=driver.is_active if hasattr(driver, "is_active") else True,
        onboarding_status=driver.onboarding_status or "pending_docs",
        live_status=driver.live_status or "offline",
        vehicle_type=driver.vehicle_type,
        vehicle_brand=driver.vehicle_brand,
        vehicle_model=driver.vehicle_model,
        vehicle_number=driver.vehicle_number,
        vehicle_color=driver.vehicle_color,
        profile_photo_url=driver.profile_photo_url,
        driving_license_url=driver.driving_license_url,
        rc_book_url=driver.rc_book_url,
        insurance_url=driver.insurance_url,
        pan_card_url=driver.pan_card_url,
        aadhar_card_url=driver.aadhar_card_url,
        puc_certificate_url=driver.puc_certificate_url,
        rating=driver.rating if hasattr(driver, "rating") else 0.0,
        total_deliveries=driver.total_deliveries if hasattr(driver, "total_deliveries") else 0,
    )
    db.add(db_driver)
    db.commit()
    db.refresh(db_driver)
    return db_driver


def update_driver(db: Session, db_driver: Driver, updates: DriverUpdate):
    if hasattr(updates, "model_dump"):
        data = updates.model_dump(exclude_unset=True)
    else:
        data = updates.dict(exclude_unset=True)

    for key, value in data.items():
        setattr(db_driver, key, value)
    db.add(db_driver)
    db.commit()
    db.refresh(db_driver)
    return db_driver


def delete_driver(db: Session, db_driver: Driver):
    db.delete(db_driver)
    db.commit()
