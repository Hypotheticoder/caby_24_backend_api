from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.security import create_access_token
from database import get_db
from models.admin import AdminUser
from schemas.admin import AdminCreate, AdminLogin, AdminRead, Token

router = APIRouter(prefix="/admin/auth", tags=["admin_auth"])


@router.post("/login", response_model=Token)
def login_admin(credentials: AdminLogin, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.email == credentials.email).first()

    if not admin or admin.password != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not admin.is_active:
        raise HTTPException(status_code=400, detail="Inactive admin account")

    access_token = create_access_token(
        data={"sub": admin.email, "role": admin.role, "id": str(admin.id)}
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/setup", response_model=AdminRead)
def create_first_admin(payload: AdminCreate, db: Session = Depends(get_db)):
    """
    Use this endpoint ONCE to create your root admin account.
    """
    existing_admin = db.query(AdminUser).filter(AdminUser.email == payload.email).first()
    if existing_admin:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_admin = AdminUser(
        name=payload.name,
        email=payload.email,
        password=payload.password,
        role=payload.role,
    )

    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    return new_admin
