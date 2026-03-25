from sqlalchemy.orm import Session
from models.user import User
from schemas.user import UserCreate, UserUpdate


def get_user(db: Session, user_id: str):
    return db.query(User).filter(User.id == user_id).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, user: UserCreate):
    db_user = User(
        name=user.name,
        phone=user.phone,
        role=user.role,
        email=user.email,
        photo_url=user.photo_url,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, db_user: User, updates: UserUpdate):
    # support Pydantic v2 (`model_dump`) and v1 (`dict`)
    if hasattr(updates, "model_dump"):
        data = updates.model_dump(exclude_unset=True)
    else:
        data = updates.dict(exclude_unset=True)

    for key, value in data.items():
        setattr(db_user, key, value)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, db_user: User):
    db.delete(db_user)
    db.commit()
