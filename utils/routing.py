import os
import httpx


async def calculate_osrm_route(pickup_lat: float, pickup_lng: float, drop_lat: float, drop_lng: float) -> dict:
    """Call an OSRM-compatible router to get a polyline and distance.

    Returns a dict with keys: `polyline`, `distance_km`, `duration_mins`, `fee`.
    On failure returns a safe fallback with `polyline` = None and `fee` = 0.0.
    """
    osrm_base = os.getenv("OSRM_URL", "http://router.project-osrm.org")
    url = f"{osrm_base}/route/v1/driving/{pickup_lng},{pickup_lat};{drop_lng},{drop_lat}?overview=full&geometries=polyline&steps=false"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            routes = data.get("routes") or []
            if not routes:
                raise RuntimeError("no routes returned from OSRM")
            route = routes[0]
            polyline = route.get("geometry")
            distance_m = route.get("distance", 0.0)
            distance_km = float(distance_m) / 1000.0
            duration_s = route.get("duration", 0.0)
            duration_mins = int(round(float(duration_s) / 60.0)) if duration_s is not None else 0

            # Simple fare calculation; override via env if desired
            base_fare = float(os.getenv("OSRM_BASE_FARE", "30.0"))
            per_km = float(os.getenv("OSRM_PER_KM", "15.0"))
            fee = round(base_fare + per_km * distance_km, 2)

            return {
                "polyline": polyline,
                "distance_km": round(distance_km, 2),
                "duration_mins": duration_mins,
                "fee": fee,
            }

    except Exception as e:
        print(f"calculate_osrm_route failed: {e}")
        return {"polyline": None, "distance_km": 0.0, "duration_mins": 0, "fee": 0.0}
