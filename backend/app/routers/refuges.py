"""
US 2.1 - Find Nearby Sensory Refuge Locations.

Reads from the `location` / `support_location` tables (parks, libraries,
quiet public spaces) per the ERD. Falls back to the Prototype slide's
fixture list (City Library / Park / Albert Park) when the table is empty,
so the frontend has something to render before the real dataset is loaded.
"""

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/refuges", tags=["refuges"])

REFUGE_CATEGORIES = {"park", "library", "quiet public space"}

_FIXTURE_REFUGES = [
    schemas.RefugeLocationOut(
        location_id=-1,
        name="City Library",
        category="library",
        eta_min=3,
        lat=-37.8102,
        lng=144.9628,
    ),
    schemas.RefugeLocationOut(
        location_id=-2, name="Park", category="park", eta_min=6, lat=-37.8110, lng=144.9640
    ),
    schemas.RefugeLocationOut(
        location_id=-3, name="Albert Park", category="park", eta_min=15, lat=-37.8432, lng=144.9700
    ),
]


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@router.get("", response_model=schemas.RefugeListResponse)
def list_refuges(
    lat: float = Query(..., description="User's current latitude"),
    lng: float = Query(..., description="User's current longitude"),
    radius_km: float = Query(1.5, description="Search radius"),
    walking_speed_kmh: float = Query(4.5),
    db: Session = Depends(get_db),
):
    locations = (
        db.query(models.Location).filter(models.Location.location_type.in_(REFUGE_CATEGORIES)).all()
    )

    # `location` table doesn't carry lat/lng in the current ERD yet, so real
    # rows can't be distance-filtered - if/when DS adds coordinates, read
    # from `locations` here instead of the fixture list below.
    del locations

    refuges = [r for r in _FIXTURE_REFUGES if _haversine_km(lat, lng, r.lat, r.lng) <= radius_km]
    # Deliberately no "or _FIXTURE_REFUGES" fallback - respecting radius_km
    # means genuinely returning an empty list when nothing is within range,
    # not silently ignoring the radius the caller asked for.

    return schemas.RefugeListResponse(refuges=refuges, generated_at=datetime.now(timezone.utc))
