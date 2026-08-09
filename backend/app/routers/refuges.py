"""
US 2.1 - Find Nearby Sensory Refuge Locations.

Reads real rows from the `location` table where `location_type='refuge'`
(confirmed via the live DB: 4 categories - Park, Library, Gallery or
museum, Quiet place of worship). `location` has real latitude/longitude
columns, so distance filtering is genuine, not a fixture.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services.geo import haversine_km

router = APIRouter(prefix="/api/refuges", tags=["refuges"])


@router.get("", response_model=schemas.RefugeListResponse)
def list_refuges(
    lat: float = Query(..., description="User's current latitude"),
    lng: float = Query(..., description="User's current longitude"),
    radius_km: float = Query(1.5, ge=0, le=10, description="Search radius (km), 0-10"),
    # gt=0 - walking_speed_kmh=0 would divide-by-zero when computing
    # eta_min below. le=15 is a sanity bound (well above any real walking
    # pace) so a typo doesn't produce a nonsense ETA.
    walking_speed_kmh: float = Query(4.5, gt=0, le=15),
    db: Session = Depends(get_db),
):
    rows = db.query(models.Location).filter(models.Location.location_type == "refuge").all()

    refuges: list[schemas.RefugeLocationOut] = []
    for row in rows:
        distance_km = haversine_km(lat, lng, row.latitude, row.longitude)
        if distance_km > radius_km:
            continue
        eta_min = (distance_km / walking_speed_kmh) * 60
        refuges.append(
            schemas.RefugeLocationOut(
                location_id=row.location_id,
                name=row.location_name,
                category=row.category or "refuge",
                eta_min=round(eta_min, 1),
                lat=row.latitude,
                lng=row.longitude,
            )
        )

    # No fixture fallback - respecting radius_km means genuinely returning
    # an empty list when nothing real is within range, not silently
    # substituting unrelated data for what the caller asked for.
    refuges.sort(key=lambda r: r.eta_min)
    return schemas.RefugeListResponse(refuges=refuges, generated_at=datetime.now(timezone.utc))
