from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from schemas.delivery import RouteRequest, RouteResponse
from utils.routing import calculate_osrm_route

router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.post("/get-route", response_model=RouteResponse, status_code=status.HTTP_200_OK)
async def get_osrm_route(req: RouteRequest) -> RouteResponse:
    result = await calculate_osrm_route(
        pickup_lat=req.pickup_lat,
        pickup_lng=req.pickup_lng,
        drop_lat=req.drop_lat,
        drop_lng=req.drop_lng,
    )

    if not result.get("polyline"):
        raise HTTPException(status_code=503, detail="Routing service unavailable")

    return RouteResponse(
        status="success",
        polyline=result["polyline"],
        distance_km=float(result.get("distance_km", 0.0)),
        estimated_mins=int(result.get("duration_mins", 0)),
        calculated_fee=float(result.get("fee", 0.0)),
    )
