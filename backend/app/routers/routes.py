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

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Address, Baseline, Location, PedestrianCountHour, PedestrianCountMinute
from app.services import routing_service, sensory_scoring
from app.services.geo import haversine_km
from app.services.scoring_config import load_scoring_config
from app.services.sensory_scoring import (
    HIGH,
    NO_DATA,
    ScoringConfig,
    SensorBaseline,
    SensorLocation,
    SensorReading,
    match_sensors_to_route,
    melbourne_baseline_slot,
)

router = APIRouter(prefix="/api/routes", tags=["routes"])


def _sensor_locations(db: Session) -> list[SensorLocation]:
    """
    Loads every *usable* sensor location once per request (the whole
    `location` table is ~273 rows total, cheap to scan) - DS3's
    `match_sensors_to_route()` does the actual distance filtering.

    Excludes placement='Indoor' sensors (confirmed via the live DB on
    2026-08-11: all 34 indoor points - libraries, community hubs, visitor
    centres - have zero rows in pedestrian_count_minute/_hour/baseline,
    while every one of the 100 outdoor points has data; Melbourne's public
    pedestrian-counting datasets only cover street-level outdoor sensors).
    Without this filter, score_route()'s all-matched-sensors-must-have-data
    rule means any route whose buffer happens to include one of these
    "ghost" sensors is permanently stuck at NO DATA, even when every real
    (outdoor) sensor nearby is scoring fine - about a quarter of all
    sensors are indoor, so this was affecting a large share of routes.
    """
    rows = (
        db.query(Location)
        .filter(Location.location_type == "sensor", Location.placement == "Outdoor")
        .all()
    )
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


def _latest_hourly_counts(db: Session, location_ids: list[int]) -> dict[str, int]:
    """
    Latest `pedestrian_count_hour` row per location, for `pedestrian_per_hour`.
    Matched-sensor lists are small (buffer radius is ~120m), so reducing in
    Python is simpler than a per-location MAX() subquery here.
    """
    if not location_ids:
        return {}
    rows = (
        db.query(PedestrianCountHour)
        .filter(PedestrianCountHour.location_id.in_(location_ids))
        .all()
    )
    latest: dict[str, tuple] = {}
    for row in rows:
        if row.pedestrian_count is None:
            continue
        key = str(row.location_id)
        candidate_key = (row.sensing_date, row.hourday)
        if key not in latest or candidate_key > latest[key][0]:
            latest[key] = (candidate_key, row.pedestrian_count)
    return {location_id: count for location_id, (_, count) in latest.items()}


# Bounding-box half-width for _nearest_address's prefilter, in degrees.
# ~0.01 deg is a little over 1km at Melbourne's latitude - generous enough
# that a real nearby address is essentially always inside the box (DS's
# `address` table has ~50k Melbourne addresses), while still cutting the
# ~50k-row table down to a small candidate set before the exact haversine
# distance is computed in Python.
_ADDRESS_SEARCH_BOX_DEG = 0.01


def _nearest_address(db: Session, lat: float, lng: float) -> str | None:
    """
    Nearest-neighbour lookup against DS's `address` table (~50k real
    Melbourne addresses with lat/lng - loaded to replace the frontend's old
    Nominatim reverse-geocoding call, confirmed via `DESCRIBE address`
    against the live DB on 2026-08-12). This is NOT `location.address` -
    that column exists on `location` but has never been populated for any
    row (0/273, confirmed against the live DB) - `address` is a separate
    table DS loaded independently.

    No spatial index on (latitude, longitude) as of writing, so this does a
    plain lat/lng bounding-box prefilter (cheap even on ~50k rows) then an
    exact haversine distance in Python for the final pick - simpler than
    teaching MySQL spatial functions for what's only ever a handful of
    lookups per request (one per route's representative sensor). Returns
    None if nothing at all falls inside the box (nothing to reasonably
    guess an address from).
    """
    box = _ADDRESS_SEARCH_BOX_DEG
    rows = (
        db.query(Address)
        .filter(
            Address.latitude.between(lat - box, lat + box),
            Address.longitude.between(lng - box, lng + box),
        )
        .all()
    )
    if not rows:
        return None
    nearest = min(rows, key=lambda row: haversine_km(lat, lng, row.latitude, row.longitude))
    return nearest.address_pnt


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


def _representative_sensor(
    status: str,
    matched_ids: Sequence[str],
    readings: Mapping[str, SensorReading],
    baselines: Mapping[str, SensorBaseline],
    config: ScoringConfig,
) -> str | None:
    """
    Pick the matched sensor whose reading is surfaced as sensory_value /
    address_pnt / pedestrian_per_min / pedestrian_per_hour on the response.

    Review round 5 (PR feedback), two issues fixed here:

    1. NO DATA must mean all four fields are null, full stop - regardless
       of whether *some* matched sensor happens to have a reading (another
       matched sensor could still be missing a baseline, stale, etc. -
       score_route()'s all-matched-sensors-must-be-valid rule is what
       actually decided NO DATA, so this must agree with it exactly rather
       than re-deriving a different, looser condition from `readings`
       alone).
    2. For HIGH, the busiest raw reading is not necessarily what caused
       the HIGH - a sensor can have a huge current_count but an even
       bigger baseline (so it fails the *relative* threshold) while a
       smaller, spikier sensor is the one that actually satisfies both of
       score_route's conditions. This mirrors that same
       both-conditions check exactly (same fields, same operators) so the
       two can never disagree.

    LOW is the remaining case (every matched sensor is guaranteed to have
    a valid reading+baseline there - score_route only returns LOW once
    that holds for all of them): picks whichever sensor's
    current_count/baseline.median_count ratio is highest, i.e. the one
    closest to (without reaching) HIGH - the most informative "worst
    case" reading to surface for an otherwise-LOW route.
    """
    if status == NO_DATA:
        return None

    sensor_ids = [
        sensor_id
        for sensor_id in dict.fromkeys(matched_ids)
        if sensor_id in readings and sensor_id in baselines
    ]
    if not sensor_ids:
        return None

    if status == HIGH:
        high_sensor_ids = [
            sensor_id
            for sensor_id in sensor_ids
            if readings[sensor_id].current_count >= config.absolute_threshold
            and readings[sensor_id].current_count
            >= baselines[sensor_id].median_count * config.relative_threshold
        ]
        # high_sensor_ids is never empty here in practice - score_route only
        # returns HIGH when it isn't, given the same matched_ids/readings/
        # baselines/config. The `or sensor_ids` fallback is defensive only.
        candidates = high_sensor_ids or sensor_ids
        return max(candidates, key=lambda sensor_id: readings[sensor_id].current_count)

    # LOW - every matched sensor here is guaranteed a valid, positive
    # baseline.median_count by score_route's own checks, so no
    # divide-by-zero guard is needed.
    return max(
        sensor_ids,
        key=lambda sensor_id: readings[sensor_id].current_count
        / baselines[sensor_id].median_count,
    )


@router.post("/compare", response_model=schemas.RouteCompareResponse)
def compare_routes(payload: schemas.RouteCompareRequest, db: Session = Depends(get_db)):
    candidates = routing_service.get_candidate_routes(
        payload.origin_lat, payload.origin_lng, payload.destination_lat, payload.destination_lng
    )

    cfg = load_scoring_config(db)
    now = datetime.now(timezone.utc)
    day_of_week, hourday = melbourne_baseline_slot(now)
    sensors = _sensor_locations(db)
    sensor_by_id = {sensor.sensor_id: sensor for sensor in sensors}

    options: list[schemas.RouteOption] = []
    for candidate in candidates:
        matched_ids = match_sensors_to_route(candidate.geometry, sensors, cfg.buffer_radius_m)
        matched_location_ids = [int(sid) for sid in matched_ids]
        readings = _latest_readings(db, matched_location_ids)
        baselines = _baselines_for_slot(db, matched_location_ids, day_of_week, hourday)
        hourly_counts = _latest_hourly_counts(db, matched_location_ids)
        status, notification = sensory_scoring.score_route(
            matched_ids, readings, baselines, cfg, now
        )

        avoided_corridor = None
        if status == sensory_scoring.HIGH:
            avoided_corridor = candidate.label

        representative_id = _representative_sensor(status, matched_ids, readings, baselines, cfg)

        sensory_value = None
        address_pnt = None
        pedestrian_per_min = None
        pedestrian_per_hour = None
        if representative_id is not None:
            reading = readings[representative_id]
            sensory_value = reading.current_count
            pedestrian_per_min = reading.current_count
            pedestrian_per_hour = hourly_counts.get(representative_id)
            sensor_location = sensor_by_id.get(representative_id)
            if sensor_location is not None:
                address_pnt = _nearest_address(
                    db, sensor_location.latitude, sensor_location.longitude
                )

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
                sensory_value=sensory_value,
                address_pnt=address_pnt,
                pedestrian_per_min=pedestrian_per_min,
                pedestrian_per_hour=pedestrian_per_hour,
            )
        )

    return schemas.RouteCompareResponse(routes=options, generated_at=datetime.now(timezone.utc))
