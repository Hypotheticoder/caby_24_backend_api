from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from schemas.delivery import RouteRequest, RouteResponse
from utils.routing import calculate_osrm_route

logger = logging.getLogger(__name__)

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


@router.get("/get-directions", status_code=status.HTTP_200_OK)
async def get_google_directions(
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lng: float = Query(..., ge=-180, le=180),
    dest_lat: float = Query(..., ge=-90, le=90),
    dest_lng: float = Query(..., ge=-180, le=180),
):
    """Get an encoded polyline between two points using Google Directions API.

    To keep the route updated as the driver moves, call this endpoint repeatedly
    with the driver's latest (origin_lat/origin_lng).
    """
    api_key = (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="Google Maps API Key missing from backend")

    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{origin_lat},{origin_lng}",
        "destination": f"{dest_lat},{dest_lng}",
        "mode": "driving",
        "key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        google_status = data.get("status")
        if google_status != "OK":
            error_message = data.get("error_message")

            status_code = 400
            if google_status == "OVER_QUERY_LIMIT":
                status_code = 429
            elif google_status == "REQUEST_DENIED":
                status_code = 403
            elif google_status == "ZERO_RESULTS":
                status_code = 404

            logger.warning(
                "Google Directions failed: status=%s message=%s",
                google_status,
                error_message,
            )

            raise HTTPException(
                status_code=status_code,
                detail={
                    "google_status": google_status,
                    "error_message": error_message,
                },
            )

        route = (data.get("routes") or [])[0]
        leg = (route.get("legs") or [])[0]

        return {
            "encoded_polyline": (route.get("overview_polyline") or {}).get("points"),
            "distance_text": (leg.get("distance") or {}).get("text"),
            "duration_text": (leg.get("duration") or {}).get("text"),
        }

    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Google routing service unavailable")
