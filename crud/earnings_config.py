from sqlalchemy.orm import Session
from models.earnings_config import EarningsConfig
from schemas.earnings_config import EarningsConfigUpdateRequest, EarningsConfigBase

def list_earnings_configs(db: Session):
    return db.query(EarningsConfig).all()

def get_earnings_config(db: Session, config_id: str):
    return db.query(EarningsConfig).filter(EarningsConfig.id == config_id).first()

def update_earnings_config(db: Session, db_config: EarningsConfig, updates: EarningsConfigUpdateRequest):
    db_config.base_fare = updates.base_fare
    db_config.per_km_rate = updates.per_km_rate
    db_config.minimum_fare = updates.minimum_fare
    db_config.platform_commission = updates.platform_commission

    db.commit()
    db.refresh(db_config)
    return db_config

# NEW: Used to add the first rows into your empty database
def create_earnings_config(db: Session, config_in: EarningsConfigBase):
    db_config = EarningsConfig(
        service_type=config_in.service_type,
        is_peak_time=config_in.is_peak_time,
        base_fare=config_in.base_fare,
        per_km_rate=config_in.per_km_rate,
        minimum_fare=config_in.minimum_fare,
        platform_commission=config_in.platform_commission
    )
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config