from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
import json

from database import get_db
from core.security_logic import r
from models.customer_order import CustomerOrder
from models.driver import Driver
from models.user import User


router = APIRouter(prefix="/search", tags=["search"])


@router.get("/find")
def global_search(
    q: str = Query(..., min_length=3, max_length=50, description="Search term"),
    skip: int = Query(0, ge=0, description="How many records to skip (Offset)"),
    limit: int = Query(10, ge=1, le=50, description="Maximum records to return (Max 50)"),
    db: Session = Depends(get_db),
):
    search_term = q.strip().lower()

    cache_key = f"search:global:{search_term}:s{skip}:l{limit}"
    cached_result = r.get(cache_key)
    if cached_result:
        print("\ud83d\ude80 Served from Redis Cache!")
        return json.loads(cached_result)

    try:
        orders = (
            db.query(CustomerOrder)
            .filter(
                or_(
                    CustomerOrder.id.ilike(f"%{search_term}%"),
                    CustomerOrder.pickup_address.ilike(f"%{search_term}%"),
                    CustomerOrder.drop_address.ilike(f"%{search_term}%"),
                    CustomerOrder.pickup_contact_name.ilike(f"%{search_term}%"),
                    CustomerOrder.pickup_contact_phone.ilike(f"%{search_term}%"),
                    CustomerOrder.status.ilike(f"%{search_term}%"),
                    CustomerOrder.assigned_driver_name.ilike(f"%{search_term}%"),
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

        drivers = (
            db.query(Driver)
            .filter(
                or_(
                    Driver.id.ilike(f"%{search_term}%"),
                    Driver.name.ilike(f"%{search_term}%"),
                    Driver.phone_number.ilike(f"%{search_term}%"),
                    Driver.firebase_uid.ilike(f"%{search_term}%"),
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

        customers = (
            db.query(User)
            .filter(
                or_(
                    User.id.ilike(f"%{search_term}%"),
                    User.name.ilike(f"%{search_term}%"),
                    User.phone.ilike(f"%{search_term}%"),
                    User.email.ilike(f"%{search_term}%"),
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

        results = {
            "query": search_term,
            "skip": skip,
            "limit": limit,
            "orders": [
                {
                    "id": o.id,
                    "type": o.order_type,
                    "status": o.status,
                    "pickup": o.pickup_address,
                }
                for o in orders
            ],
            "drivers": [
                {"id": d.id, "name": d.name, "phone": d.phone_number} for d in drivers
            ],
            "customers": [
                {"id": c.id, "name": c.name, "phone": c.phone} for c in customers
            ],
        }

        r.setex(cache_key, 60, json.dumps(results))

        return results

    except Exception as e:
        print(f"Search Error: {e}")
        raise HTTPException(status_code=500, detail="Search engine overloaded. Try again.")
