"""
US 1.1 - Display Route Sensory Level (route comparison)
US 1.2 - Avoid Highly Congested Areas (congestion-aware route + text notification)

Both live on one endpoint: the frontend's "Plan" screen shows the same
route list either way, just annotated with LOW/HIGH/NO DATA and, for the
recommended route, a text notification when a corridor was avoided.
Per the prototype ("notifying the user by text, not voice") notifications
are plain text fields, not push/audio.

Sensor matching against real data (replaces the earlier
`_fixture_sensor_data_for` placeholder): the shared DB has no separate
`sensors` table - a `location` row with `location_type='sensor'` IS a
pedestrian-counting point, keyed by `location_id`. "Matched to this
route" means within `SENSOR_MATCH_RADIUS_KM` of any point on the route's
polyline (confirmed schema via live `DESCRIBE`, see app/models.py).
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import get_settings
from app.database import get_db
from app.models import Baseline, Location, PedestrianCountMinute
from app.services import routing_service, sensory_scoring
from app.services.geo import haversine_km
from app.services.sensory_scoring import SensorBaseline, SensorReading

router = APIRouter(prefix="/api/routes", tags=["routes"])


def _match_sensors_to_route(db: Session, geometry: list[list[float]]) -> list[Location]:
    """
    Loads every sensor location once (the whole `location` table is ~273
    rows total, cheap to scan) and does the distance check in Python -
    there's no spatial index/extension set up on the shared MySQL
    instance, so this isn't a spatial SQL query.
    """
    settings = get_settings()
    sensors = db.query(Location).filter(Location.location_type == "sensor").all()

    matched: list[Location] = []
    for sensor in sensors:
        for lat, lng in geometry:
            if haversine_km(lat, lng, sensor.latitude, sensor.longitude) <= (
                settings.sensor_match_radius_km
            ):
                matched.append(sensor)
                break
    return matched


def _real_sensor_data_for(
    db: Session, sensors: list[Location]
) -> tuple[list[str], dict[str, SensorReading], dict[str, SensorBaseline]]:
    settings = get_settings()
    location_ids = [s.location_id for s in sensors]
    matched_ids = [str(lid) for lid in location_ids]
    if not location_ids:
        return matched_ids, {}, {}

    now_local = datetime.now(ZoneInfo(settings.local_timezone))
    # ASSUMPTION: baseline.day_of_week follows Python's datetime.weekday()
    # convention (Monday=0 .. Sunday=6) - confirmed the column only holds
    # 0-6, but not confirmed which day is 0. If routes near a known-busy
    # time score LOW when they shouldn't, this is the first thing to flip
    # (swap for `(now_local.weekday() + 1) % 7` to shift by a day).
    day_of_week = now_local.weekday()
    hourday = now_local.hour

    baseline_rows = (
        db.query(Baseline)
        .filter(
            Baseline.location_id.in_(location_ids),
            Baseline.day_of_week == day_of_week,
            Baseline.hourday == hourday,
        )
        .all()
    )
    baselines = {
        str(b.location_id): SensorBaseline(str(b.location_id), b.median_count, b.observation_count)
        for b in baseline_rows
    }

    # Latest reading per location. A window function (ROW_NUMBER() OVER
    # PARTITION BY location_id) would batch this into one query, but
    # SQLite (used in tests) only supports window functions in newer
    # versions - a plain per-location "most recent row" loop keeps this
    # portable, and 273 locations is small enough that it's not a real
    # cost here.
    readings: dict[str, SensorReading] = {}
    for location_id in location_ids:
        latest = (
            db.query(PedestrianCountMinute)
            .filter(PedestrianCountMinute.location_id == location_id)
            .order_by(PedestrianCountMinute.sensing_datetime.desc())
            .first()
        )
        if latest is not None and latest.total_of_directions is not None:
            sid = str(location_id)
            readings[sid] = SensorReading(sid, latest.total_of_directions)

    return matched_ids, readings, baselines


@router.post("/compare", response_model=schemas.RouteCompareResponse)
def compare_routes(payload: schemas.RouteCompareRequest, db: Session = Depends(get_db)):
    candidates = routing_service.get_candidate_routes(
        payload.origin_lat, payload.origin_lng, payload.destination_lat, payload.destination_lng
    )

    options: list[schemas.RouteOption] = []
    for candidate in candidates:
        sensors = _match_sensors_to_route(db, candidate.geometry)
        matched_ids, readings, baselines = _real_sensor_data_for(db, sensors)
        status, notification = sensory_scoring.score_route(matched_ids, readings, baselines)

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
