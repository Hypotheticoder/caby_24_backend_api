from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

router = APIRouter(prefix="/delivery", tags=["delivery"])


class RouteRequest(BaseModel):
    pickup_lat: float
    pickup_lng: float
    drop_lat: float
    drop_lng: float


@router.post("/get-route")
async def get_osrm_route(req: RouteRequest):
    # OSRM expects Longitude,Latitude coordinates!
    coordinates = f"{req.pickup_lng},{req.pickup_lat};{req.drop_lng},{req.drop_lat}"
    
    # Use overview=full so the polyline perfectly follows the curves of the roads.
    osrm_url = f"http://router.project-osrm.org/route/v1/driving/{coordinates}?overview=full"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(osrm_url, timeout=10.0)
            response.raise_for_status() 
        except httpx.RequestError as exc:
            print(f"An error occurred while requesting OSRM: {exc}")
            raise HTTPException(status_code=503, detail="Routing service unavailable")
        except httpx.HTTPStatusError as exc:
            print(f"OSRM returned a failure status: {exc.response.status_code}")
            raise HTTPException(status_code=502, detail="Routing service failed to calculate route")

    data = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise HTTPException(status_code=400, detail="Could not find a valid driving route between these points.")

    # Extract the prime route data
    route = data["routes"][0]
    encoded_polyline = route["geometry"]
    
    # Distance is returned in meters, duration in seconds
    distance_km = round(route["distance"] / 1000, 2)
    duration_mins = round(route["duration"] / 60)

    # Simplified Indian Rupee Fee Calculation: ₹30 base fare + ₹15 per km
    delivery_fee = 30 + (distance_km * 15)

    return {
        "status": "success",
        "polyline": encoded_polyline,
        "distance_km": distance_km,
        "estimated_mins": duration_mins,
        "calculated_fee": round(delivery_fee, 2)
    }
