from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from database import get_db
from schemas.earnings_config import EarningsConfigRead, EarningsConfigUpdateRequest, EarningsConfigBase
import crud.earnings_config as crud_earnings_config
from datetime import datetime, timedelta

router = APIRouter(prefix="/admin/earnings", tags=["Admin Earnings"])


# 1. GET ALL PRICING MENUS (For Flutter Admin Table)
@router.get("/list", response_model=List[EarningsConfigRead])
def get_all_earnings_configs(db: Session = Depends(get_db)):
    configs = crud_earnings_config.list_earnings_configs(db)
    return configs


# 2. UPDATE A SPECIFIC PRICE MENU (When Admin hits Save)
@router.put("/{config_id}", response_model=EarningsConfigRead)
def update_earnings_config(
    config_id: str,
    updates: EarningsConfigUpdateRequest,
    db: Session = Depends(get_db)
):
    config = crud_earnings_config.get_earnings_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Earnings configuration not found")
    updated_config = crud_earnings_config.update_earnings_config(db, config, updates)
    return updated_config


# 3. CREATE INITIAL PRICING (Use this in FastAPI /docs to add the PDF data!)
@router.post("/create", response_model=EarningsConfigRead)
def create_initial_config(
    new_config: EarningsConfigBase,
    db: Session = Depends(get_db)
):
    return crud_earnings_config.create_earnings_config(db, new_config)


# 4. EARNINGS SUMMARY (For Flutter Admin Earnings Screen)
@router.get("/summary")
def get_earnings_summary(
    period: str = Query("daily", description="daily | weekly | monthly | yearly"),
    db: Session = Depends(get_db)
):
    CustomerOrder = __import__("models.customer_order", fromlist=["CustomerOrder"]).CustomerOrder

    # Calculate date range based on period
    now = datetime.utcnow()
    if period == "daily":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        start_date = now - timedelta(days=7)
    elif period == "monthly":
        start_date = now - timedelta(days=30)
    elif period == "yearly":
        start_date = now - timedelta(days=365)
    else:
        raise HTTPException(status_code=400, detail="Invalid period. Use daily, weekly, monthly, or yearly.")

    # Query completed orders within date range
    completed_statuses = ["DELIVERED", "COMPLETED"]
    orders = db.query(CustomerOrder).filter(
        CustomerOrder.created_at >= start_date,
        CustomerOrder.status.in_(completed_statuses)
    ).all()

    # Calculate revenue breakdown
    cab_revenue = 0.0
    bike_revenue = 0.0
    parcel_revenue = 0.0
    total_gst = 0.0
    total_commission = 0.0
    total_driver_payout = 0.0

    for order in orders:
        total_fare = float(order.total_fare or 0)
        gst = float(order.gst_amount or 0)
        commission = float(order.platform_commission or 0)
        payout = float(order.driver_payout or 0)

        vehicle = (order.vehicle_type or "").lower()

        if "cab" in vehicle or "ride" in vehicle:
            cab_revenue += total_fare
        elif "bike" in vehicle:
            bike_revenue += total_fare
        elif "parcel" in vehicle:
            parcel_revenue += total_fare

        total_gst += gst
        total_commission += commission
        total_driver_payout += payout

    total_revenue = cab_revenue + bike_revenue + parcel_revenue

    return {
        "period": period,
        "start_date": start_date.isoformat(),
        "cab_revenue": round(cab_revenue, 2),
        "bike_revenue": round(bike_revenue, 2),
        "parcel_revenue": round(parcel_revenue, 2),
        "total_revenue": round(total_revenue, 2),
        "total_gst": round(total_gst, 2),
        "total_commission": round(total_commission, 2),
        "total_driver_payout": round(total_driver_payout, 2),
        "order_count": len(orders),
    }