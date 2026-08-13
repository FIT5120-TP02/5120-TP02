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

import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Address, Baseline, Location, PedestrianCountMinute
from app.services import routing_service, sensory_scoring
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


def _latest_hourly_counts(db: Session, readings: Mapping[str, SensorReading]) -> dict[str, int]:
    """
    Trailing 60-minute pedestrian total per location, for `pedestrian_per_hour`
    - summed directly from `pedestrian_count_minute`, the same near-real-time
    source `_latest_readings` reads (DS1's `poll_minutes` refreshes it every
    15 min, keeping a 6h rolling window per sensor).

    The window for each sensor ends at *that sensor's own* latest reading
    (`readings[sensor_id].observed_at`, already fetched by `_latest_readings`)
    rather than the API server's wall-clock `now`. This was tried first with
    a shared `now` anchor and broke live: a sensor whose `pedestrian_per_min`
    reading was fresh enough to pass score_route's 30-minute staleness check
    still came back with `pedestrian_per_hour=null` (zero rows matched) -
    DS1's ingestion job runs on its own machine/clock, and any skew against
    the API server's clock is enough to push a sensor's actual latest row
    just outside a window measured from the server's `now`. Anchoring on the
    sensor's own timestamp instead means the latest reading is trivially
    always inside its own window (comparisons are naive-DB-value vs.
    naive-DB-value, never against a live server clock), so
    `pedestrian_per_hour` can never be null while `pedestrian_per_min` has a
    value for that same sensor.

    Previously this read the *latest* row of `pedestrian_count_hour` instead
    - DS1's one-year historical archive, batch-loaded roughly daily via
    `load_hours()`. That "latest" row could be from hours or days ago,
    completely unaligned with `pedestrian_per_min`'s near-real-time reading,
    which is exactly what produced reports like "49/min but 21/hour" for the
    same sensor.
    """
    location_ids = [
        int(sensor_id) for sensor_id, reading in readings.items() if reading.observed_at is not None
    ]
    if not location_ids:
        return {}
    rows = (
        db.query(PedestrianCountMinute)
        .filter(
            PedestrianCountMinute.location_id.in_(location_ids),
            PedestrianCountMinute.total_of_directions.isnot(None),
        )
        .all()
    )
    totals: dict[str, int] = {}
    for row in rows:
        sensor_id = str(row.location_id)
        reading = readings.get(sensor_id)
        if reading is None or reading.observed_at is None:
            continue
        window_start = reading.observed_at - timedelta(hours=1)
        if window_start < row.sensing_datetime <= reading.observed_at:
            totals[sensor_id] = totals.get(sensor_id, 0) + row.total_of_directions
    return totals


def _hourly_readings(
    readings: Mapping[str, SensorReading], hourly_counts: Mapping[str, int]
) -> dict[str, SensorReading]:
    """The same sensors, measured over an hour instead of over one minute.

    score_route compares current_count against two limits DS2 calibrated on
    the HOURLY table: absolute_threshold (500) and baseline.median_count *
    1.5 (ds2-baseline/threshold_analysis.py:20,36). Handing it a single
    minute made that comparison ~60x too small - across 18,992 live
    minute-readings exactly one ever reached 500, on one sensor out of 99, so
    HIGH was not rare, it was unreachable, and every route came back LOW or
    NO DATA no matter how busy the street was.

    `_latest_hourly_counts` already computes the trailing-hour total for
    `pedestrian_per_hour`, so this only restates it in the shape score_route
    takes. observed_at is carried through unchanged - freshness is still
    judged by when the sensor last reported, not by the window's length.
    """
    return {
        sensor_id: SensorReading(sensor_id, float(total), readings[sensor_id].observed_at)
        for sensor_id, total in hourly_counts.items()
        if sensor_id in readings
    }


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

    There is no index on (latitude, longitude), so the box filter cannot be
    served by one - EXPLAIN reports `type: ALL` over all 48,762 rows either
    way. What matters is how many rows come BACK. Ranking in Python meant
    shipping every row in the box to the app and building an ORM object for
    each: in the CBD that box holds 13,154 addresses, and this runs once per
    candidate route. On the deployed instance a single /compare took 79
    seconds, against 0.5s for endpoints reading the same database. Ordering
    in SQL returns one row instead.

    Returns None if nothing falls inside the box (nothing to reasonably
    guess an address from).
    """
    box = _ADDRESS_SEARCH_BOX_DEG
    # A degree of longitude is shorter than a degree of latitude (~0.79x at
    # Melbourne), so raw degree distance would stretch "nearest" east-west.
    # Scale longitude by cos(lat). Squared, to keep this to arithmetic every
    # backend understands - MySQL in production, SQLite under test.
    lng_scale = math.cos(math.radians(lat)) ** 2
    lat_delta = Address.latitude - lat
    lng_delta = Address.longitude - lng
    row = (
        db.query(Address.address_pnt)
        .filter(
            Address.latitude.between(lat - box, lat + box),
            Address.longitude.between(lng - box, lng + box),
        )
        .order_by(lat_delta * lat_delta + lng_delta * lng_delta * lng_scale)
        .first()
    )
    return row[0] if row else None


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
        key=lambda sensor_id: readings[sensor_id].current_count / baselines[sensor_id].median_count,
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
        hourly_counts = _latest_hourly_counts(db, readings)
        # Scored on the hourly figure, because that is the unit DS2's
        # thresholds are in. `readings` stays per-minute for display below.
        scored = _hourly_readings(readings, hourly_counts)
        status, notification = sensory_scoring.score_route(matched_ids, scored, baselines, cfg, now)

        avoided_corridor = None
        if status == sensory_scoring.HIGH:
            avoided_corridor = candidate.label

        representative_id = _representative_sensor(status, matched_ids, scored, baselines, cfg)

        sensory_value = None
        address_pnt = None
        pedestrian_per_min = None
        pedestrian_per_hour = None
        if representative_id is not None:
            # sensory_value is the number the status was decided on, so it
            # follows the scored figure rather than the raw minute.
            sensory_value = scored[representative_id].current_count
            pedestrian_per_min = readings[representative_id].current_count
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
