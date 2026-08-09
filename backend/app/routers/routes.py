"""
US 1.1 - Display Route Sensory Level (route comparison)
US 1.2 - Avoid Highly Congested Areas (congestion-aware route + text notification)

Both live on one endpoint: the frontend's "Plan" screen shows the same
route list either way, just annotated with LOW/HIGH/NO DATA and, for the
recommended route, a text notification when a corridor was avoided.
Per the prototype ("notifying the user by text, not voice") notifications
are plain text fields, not push/audio.

Sensor scoring uses DS3's approved implementation
(app/services/sensory_scoring.py, ported verbatim from PR #4 per review
round 3, issue #1) - this module's job is just the SQLAlchemy glue: fetch
sensor locations/readings/baselines from the shared DB (a `location` row
with `location_type='sensor'` IS a pedestrian-counting point - there's no
separate `sensors` table) and hand them to DS3's pure
`match_sensors_to_route()`/`score_route()` functions unchanged.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Baseline, Location, PedestrianCountMinute
from app.services import routing_service, sensory_scoring
from app.services.scoring_config import load_scoring_config
from app.services.sensory_scoring import (
    SensorBaseline,
    SensorLocation,
    SensorReading,
    match_sensors_to_route,
    melbourne_baseline_slot,
)

router = APIRouter(prefix="/api/routes", tags=["routes"])


def _sensor_locations(db: Session) -> list[SensorLocation]:
    """
    Loads every sensor location once per request (the whole `location`
    table is ~273 rows total, cheap to scan) - DS3's
    `match_sensors_to_route()` does the actual distance filtering.
    """
    rows = db.query(Location).filter(Location.location_type == "sensor").all()
    return [SensorLocation(str(row.location_id), row.latitude, row.longitude) for row in rows]


def _latest_readings(db: Session, location_ids: list[int]) -> dict[str, SensorReading]:
    """
    One batched query for "the latest pedestrian_count_minute row per
    location" (a join against a per-location MAX(sensing_datetime)
    subquery), rather than one query per sensor.
    """
    if not location_ids:
        return {}
    latest_per_location = (
        db.query(
            PedestrianCountMinute.location_id,
            func.max(PedestrianCountMinute.sensing_datetime).label("latest_dt"),
        )
        .filter(PedestrianCountMinute.location_id.in_(location_ids))
        .group_by(PedestrianCountMinute.location_id)
        .subquery()
    )
    rows = (
        db.query(PedestrianCountMinute)
        .join(
            latest_per_location,
            (PedestrianCountMinute.location_id == latest_per_location.c.location_id)
            & (PedestrianCountMinute.sensing_datetime == latest_per_location.c.latest_dt),
        )
        .all()
    )
    return {
        str(row.location_id): SensorReading(
            str(row.location_id), row.total_of_directions, row.sensing_datetime
        )
        for row in rows
        if row.total_of_directions is not None
    }


def _baselines_for_slot(
    db: Session, location_ids: list[int], day_of_week: int, hourday: int
) -> dict[str, SensorBaseline]:
    if not location_ids:
        return {}
    rows = (
        db.query(Baseline)
        .filter(
            Baseline.location_id.in_(location_ids),
            Baseline.day_of_week == day_of_week,
            Baseline.hourday == hourday,
        )
        .all()
    )
    return {
        str(row.location_id): SensorBaseline(
            str(row.location_id), row.median_count, row.observation_count
        )
        for row in rows
    }


@router.post("/compare", response_model=schemas.RouteCompareResponse)
def compare_routes(payload: schemas.RouteCompareRequest, db: Session = Depends(get_db)):
    candidates = routing_service.get_candidate_routes(
        payload.origin_lat, payload.origin_lng, payload.destination_lat, payload.destination_lng
    )

    cfg = load_scoring_config(db)
    now = datetime.now(timezone.utc)
    day_of_week, hourday = melbourne_baseline_slot(now)
    sensors = _sensor_locations(db)

    options: list[schemas.RouteOption] = []
    for candidate in candidates:
        matched_ids = match_sensors_to_route(candidate.geometry, sensors, cfg.buffer_radius_m)
        matched_location_ids = [int(sid) for sid in matched_ids]
        readings = _latest_readings(db, matched_location_ids)
        baselines = _baselines_for_slot(db, matched_location_ids, day_of_week, hourday)
        status, notification = sensory_scoring.score_route(
            matched_ids, readings, baselines, cfg, now
        )

        avoided_corridor = None
        if status == sensory_scoring.HIGH:
            avoided_corridor = candidate.label

        options.append(
            schemas.RouteOption(
                route_id=candidate.route_id,
                label=candidate.label,
                distance_km=candidate.distance_km,
                duration_min=candidate.duration_min,
                sensory_status=status,
                geometry=candidate.geometry,
                avoided_corridor=avoided_corridor,
                notification=notification,
            )
        )

    return schemas.RouteCompareResponse(routes=options, generated_at=datetime.now(timezone.utc))
