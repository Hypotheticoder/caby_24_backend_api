from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
from models.user import User
from schemas.user import UserCreate, UserRead, UserUpdate
import crud.user as crud_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/create", response_model=UserRead)
def create_user_endpoint(user: UserCreate, db: Session = Depends(get_db)):
    return crud_user.create_user(db, user)


@router.get("/list", response_model=List[UserRead])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crud_user.get_users(db, skip, limit)


@router.get("/{user_id}", response_model=UserRead)
def get_user_endpoint(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_user = crud_user.get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.get("/me", response_model=UserRead)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    The Customer App calls this to get its own profile.
    It's secure because it uses the Firebase token.
    """
    return current_user


@router.put("/{user_id}", response_model=UserRead)
def update_user_endpoint(user_id: str, updates: UserUpdate, db: Session = Depends(get_db)):
    db_user = crud_user.get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return crud_user.update_user(db, db_user, updates)


@router.put("/me", response_model=UserRead)
def update_my_profile(
    updates: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crud_user.update_user(db, current_user, updates)


@router.delete("/{user_id}", status_code=204)
def delete_user_endpoint(user_id: str, db: Session = Depends(get_db)):
    db_user = crud_user.get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    crud_user.delete_user(db, db_user)
    return
