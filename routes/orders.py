from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from database import get_db
from schemas.order import OrderCreate, OrderRead, OrderUpdate
import crud.order as crud_order

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/create", response_model=OrderRead)
def create_order_endpoint(order: OrderCreate, db: Session = Depends(get_db)):
    return crud_order.create_order(db, order)


@router.get("/list", response_model=List[OrderRead])
def list_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_order.get_orders(db, skip, limit)


@router.get("/get/{order_id}", response_model=OrderRead)
def get_order_endpoint(order_id: int, db: Session = Depends(get_db)):
    db_order = crud_order.get_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order


@router.put("/update/{order_id}", response_model=OrderRead)
def update_order_endpoint(order_id: int, updates: OrderUpdate, db: Session = Depends(get_db)):
    db_order = crud_order.get_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    return crud_order.update_order(db, db_order, updates)


@router.delete("/delete/{order_id}", status_code=204)
def delete_order_endpoint(order_id: int, db: Session = Depends(get_db)):
    db_order = crud_order.get_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    crud_order.delete_order(db, db_order)
    return
