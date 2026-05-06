from sqlalchemy.orm import Session
from models.earnings_config import EarningsConfig
from schemas.earnings_config import EarningsConfigUpdateRequest, EarningsConfigBase

def list_earnings_configs(db: Session):
    return db.query(EarningsConfig).all()

def get_earnings_config(db: Session, config_id: str):
    return db.query(EarningsConfig).filter(EarningsConfig.id == config_id).first()

def update_earnings_config(db: Session, db_config: EarningsConfig, updates: EarningsConfigUpdateRequest):
    # Automatically apply only fields the Admin actually sent.
    # Pydantic v2: model_dump(); v1 fallback: dict().
    if hasattr(updates, "model_dump"):
        update_data = updates.model_dump(exclude_unset=True)
    else:
        update_data = updates.dict(exclude_unset=True)

    # Ignore explicit nulls to avoid overwriting NOT NULL DB columns.
    for key, value in update_data.items():
        if value is None:
            continue
        setattr(db_config, key, value)

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
        platform_commission=config_in.platform_commission,
    )

    # Optional fields: only set if provided; otherwise DB/model defaults apply.
    if getattr(config_in, "max_weight_kg", None) is not None:
        db_config.max_weight_kg = config_in.max_weight_kg
    if getattr(config_in, "max_distance_km", None) is not None:
        db_config.max_distance_km = config_in.max_distance_km
    if getattr(config_in, "pickup_radius_km", None) is not None:
        db_config.pickup_radius_km = config_in.pickup_radius_km

    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config