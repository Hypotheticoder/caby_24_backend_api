from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from database import get_db
from schemas.customer_order import (
    CustomerOrderCreate,
    CustomerOrderRead,
    CustomerOrderUpdate,
)
import crud.customer_order as crud_customer_order

router = APIRouter(prefix="/customer_orders", tags=["customer_orders"])


@router.post("/create", response_model=CustomerOrderRead)
def create_customer_order_endpoint(order: CustomerOrderCreate, db: Session = Depends(get_db)):
    return crud_customer_order.create_customer_order(db, order)


@router.get("/list", response_model=List[CustomerOrderRead])
def list_customer_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_customer_order.get_customer_orders(db, skip, limit)


@router.get("/{order_id}", response_model=CustomerOrderRead)
def get_customer_order_endpoint(order_id: str, db: Session = Depends(get_db)):
    db_order = crud_customer_order.get_customer_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order


@router.put("/{order_id}", response_model=CustomerOrderRead)
def update_customer_order_endpoint(order_id: str, updates: CustomerOrderUpdate, db: Session = Depends(get_db)):
    db_order = crud_customer_order.get_customer_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    return crud_customer_order.update_customer_order(db, db_order, updates)


@router.delete("/{order_id}", status_code=204)
def delete_customer_order_endpoint(order_id: str, db: Session = Depends(get_db)):
    db_order = crud_customer_order.get_customer_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    crud_customer_order.delete_customer_order(db, db_order)
    return
