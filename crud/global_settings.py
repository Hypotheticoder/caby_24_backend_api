from sqlalchemy.orm import Session

from models.global_settings import GlobalSetting
from schemas.global_settings import GlobalSettingCreate


def get_all_settings(db: Session):
    return db.query(GlobalSetting).all()


def get_setting(db: Session, key: str):
    return db.query(GlobalSetting).filter(GlobalSetting.key == key).first()


def upsert_setting(db: Session, setting_in: GlobalSettingCreate):
    db_setting = get_setting(db, setting_in.key)

    if db_setting:
        db_setting.value = setting_in.value
        if setting_in.description is not None:
            db_setting.description = setting_in.description
    else:
        db_setting = GlobalSetting(
            key=setting_in.key,
            value=setting_in.value,
            description=setting_in.description,
        )
        db.add(db_setting)

    db.commit()
    db.refresh(db_setting)
    return db_setting


def delete_setting(db: Session, key: str):
    db_setting = get_setting(db, key)
    if db_setting:
        db.delete(db_setting)
        db.commit()
        return True
    return False
