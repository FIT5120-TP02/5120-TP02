"""DS3 sensory scoring using the tables produced by DS1 and DS2.

Ported verbatim from DS3's approved implementation (PR #4,
`ds3-sensory-scoring/sensory_scoring.py` on `jliu0410`'s branch) per
review round 3, issue #1 - this replaces IT's earlier placeholder, which
was missing stale-reading protection, the absolute HIGH threshold, and
correct Melbourne baseline-slot handling.

`load_config`/`score_route_from_database`/`main` below use a raw pymysql
connection (matching db.py's style) and are DS3's own entry points for
batch/script use - the FastAPI integration in app/routers/routes.py uses
the pure functions (`match_sensors_to_route`, `score_route`,
`melbourne_baseline_slot`, `ScoringConfig`) with data fetched via
SQLAlchemy instead, since the app's DB session is already a SQLAlchemy
Session, not a raw pymysql connection - see routes.py for that glue.
"""

from __future__ import annotations

import math
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import pairwise
from zoneinfo import ZoneInfo

LOW = "LOW"
HIGH = "HIGH"
NO_DATA = "NO DATA"

MELBOURNE_TIMEZONE = ZoneInfo("Australia/Melbourne")
# DS1 documents sensing_datetime as a UTC value (for example, +00:00).
# MySQL DATETIME drops the offset, so naive values read back from the shared
# database must be restored as UTC before freshness comparisons.
DATABASE_TIMEZONE = timezone.utc


@dataclass(frozen=True)
class SensorLocation:
    sensor_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class SensorReading:
    sensor_id: str
    current_count: float
    observed_at: datetime | None = None


@dataclass(frozen=True)
class SensorBaseline:
    sensor_id: str
    median_count: float
    observation_count: int


@dataclass(frozen=True)
class ScoringConfig:
    buffer_radius_m: float = 120.0
    relative_threshold: float = 1.5
    absolute_threshold: float = 500.0
    # A count this high is HIGH however busy the street usually is. Without
    # it, somewhere permanently crowded can never flag: a sensor whose
    # typical hour is 1,745 needs 2,618 before the relative rule fires, so it
    # reads LOW at 1,774 - true, but not what someone sensitive to crowds is
    # asking.
    #
    # 800/hour is the 84.3rd percentile of a year of history. It leaves about
    # 15% of baseline slots permanently HIGH - the busiest corridors through
    # most of the working day - which is the deliberate trade for catching
    # streets that are crowded every day rather than only unusual ones.
    #
    # Do not set this to absolute_threshold (500). The relative branch would
    # never decide anything, since every count reaching it also clears the
    # ceiling, and the rule collapses to plain absolute scoring.
    crowded_absolute_threshold: float = 800.0
    minimum_observations: int = 10
    minimum_sensors: int = 1
    live_max_age_minutes: int = 30


def _point_segment_distance_m(point, start, end):
    """Approximate point-to-segment distance for short CBD routes."""
    reference_lat = math.radians((point[0] + start[0] + end[0]) / 3)
    metres_per_degree_lat = 111_320.0
    metres_per_degree_lng = metres_per_degree_lat * math.cos(reference_lat)
    px = (point[1] - start[1]) * metres_per_degree_lng
    py = (point[0] - start[0]) * metres_per_degree_lat
    ex = (end[1] - start[1]) * metres_per_degree_lng
    ey = (end[0] - start[0]) * metres_per_degree_lat
    length_squared = ex * ex + ey * ey
    if length_squared == 0:
        return math.hypot(px, py)
    projection = max(0.0, min(1.0, (px * ex + py * ey) / length_squared))
    return math.hypot(px - projection * ex, py - projection * ey)


def match_sensors_to_route(
    geometry: Sequence[Sequence[float]],
    sensors: Iterable[SensorLocation],
    buffer_radius_m: float = 120.0,
) -> list[str]:
    """Match sensors within the buffer of a ``[[lat, lng], ...]`` route."""
    if buffer_radius_m < 0:
        raise ValueError("buffer_radius_m cannot be negative")
    if len(geometry) < 2:
        return []
    points = [(float(point[0]), float(point[1])) for point in geometry]
    matched = []
    seen = set()
    for sensor in sensors:
        distance = min(
            _point_segment_distance_m(
                (sensor.latitude, sensor.longitude), segment_start, segment_end
            )
            for segment_start, segment_end in pairwise(points)
        )
        if distance <= buffer_radius_m and sensor.sensor_id not in seen:
            matched.append(sensor.sensor_id)
            seen.add(sensor.sensor_id)
    return matched


def _is_stale(observed_at: datetime | None, now: datetime, max_age_minutes: int) -> bool:
    if observed_at is None:
        return True
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=DATABASE_TIMEZONE)
    if now.tzinfo is None:
        now = now.replace(tzinfo=MELBOURNE_TIMEZONE)
    return now.astimezone(timezone.utc) - observed_at.astimezone(timezone.utc) > timedelta(
        minutes=max_age_minutes
    )


def melbourne_baseline_slot(when: datetime | None = None) -> tuple[int, int]:
    """Return DS2's ``(weekday, hour)`` slot in Melbourne local time.

    A supplied naive datetime is interpreted as Melbourne local time. An aware
    datetime is converted to Melbourne before selecting the baseline slot.
    """
    value = when or datetime.now(MELBOURNE_TIMEZONE)
    if value.tzinfo is None:
        value = value.replace(tzinfo=MELBOURNE_TIMEZONE)
    else:
        value = value.astimezone(MELBOURNE_TIMEZONE)
    return value.weekday(), value.hour


def score_route(
    matched_sensor_ids: Sequence[str],
    readings: Mapping[str, SensorReading],
    baselines: Mapping[str, SensorBaseline],
    config: ScoringConfig | None = None,
    now: datetime | None = None,
) -> tuple[str, str | None]:
    """Return ``(LOW|HIGH|NO DATA, notification)`` for one route.

    LOW is returned only when every matched sensor has a fresh reading and a
    reliable baseline.

    HIGH means either of two different things, and both matter:

    - the corridor is busier than it normally is at this hour (DS2's absolute
      and relative limits together), or
    - the corridor is crowded outright, regardless of what normal looks like
      there (``crowded_absolute_threshold``).

    Only the first was checked before, which left a hole: a street that is
    always busy never flags, because its own history sets the bar out of
    reach. Only the second would be worse - the busiest streets would sit at
    HIGH permanently, which tells a user nothing they cannot see on a map.
    """
    cfg = config or ScoringConfig()
    check_time = now or datetime.now(timezone.utc)
    sensor_ids = list(dict.fromkeys(str(sensor_id) for sensor_id in matched_sensor_ids))
    if len(sensor_ids) < cfg.minimum_sensors:
        return NO_DATA, None
    for sensor_id in sensor_ids:
        reading = readings.get(sensor_id)
        baseline = baselines.get(sensor_id)
        if reading is None or baseline is None:
            return NO_DATA, None
        if reading.current_count < 0:
            return NO_DATA, None
        if baseline.median_count <= 0:
            return NO_DATA, None
        if baseline.observation_count < cfg.minimum_observations:
            return NO_DATA, None
        if _is_stale(reading.observed_at, check_time, cfg.live_max_age_minutes):
            return NO_DATA, None
    unusual = [
        sensor_id
        for sensor_id in sensor_ids
        if readings[sensor_id].current_count >= cfg.absolute_threshold
        and readings[sensor_id].current_count
        >= baselines[sensor_id].median_count * cfg.relative_threshold
    ]
    if unusual:
        return (
            HIGH,
            "This route includes a corridor with unusually high pedestrian density.",
        )
    crowded = [
        sensor_id
        for sensor_id in sensor_ids
        if readings[sensor_id].current_count >= cfg.crowded_absolute_threshold
    ]
    if crowded:
        # Deliberately different wording. "Unusually high" would be false
        # here - this corridor is this busy most days, and a user deciding
        # whether to walk it deserves to know which of the two it is.
        return (
            HIGH,
            "This route includes a consistently crowded corridor.",
        )
    return LOW, None


def load_config(conn) -> ScoringConfig:
    """Load DS2 thresholds, with documented defaults for optional DS3 keys."""
    with conn.cursor() as cursor:
        cursor.execute("SELECT config_key, value FROM config")
        values = {row["config_key"]: row["value"] for row in cursor.fetchall()}
    return ScoringConfig(
        buffer_radius_m=float(values.get("route_buffer_radius_m", 120)),
        relative_threshold=float(values.get("relative_threshold", 1.5)),
        absolute_threshold=float(values.get("absolute_threshold", 500)),
        crowded_absolute_threshold=float(values.get("crowded_absolute_threshold", 800)),
        minimum_observations=int(values.get("minimum_observations", 10)),
        minimum_sensors=int(values.get("minimum_route_sensors", 1)),
        live_max_age_minutes=int(values.get("live_max_age_minutes", 30)),
    )


def score_route_from_database(
    geometry: Sequence[Sequence[float]], conn, now: datetime | None = None
) -> tuple[str, str | None]:
    """Match and score a route using the existing shared MySQL schema."""
    cfg = load_config(conn)
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT location_id, latitude, longitude FROM location "
            "WHERE location_type = 'sensor'"
        )
        sensors = [
            SensorLocation(str(row["location_id"]), row["latitude"], row["longitude"])
            for row in cursor.fetchall()
        ]
    matched = match_sensors_to_route(geometry, sensors, cfg.buffer_radius_m)
    if len(matched) < cfg.minimum_sensors:
        return NO_DATA, None
    placeholders = ", ".join(["%s"] * len(matched))
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT p.location_id, p.total_of_directions, p.sensing_datetime "
            "FROM pedestrian_count_minute p JOIN ("
            "SELECT location_id, MAX(sensing_datetime) AS newest "
            f"FROM pedestrian_count_minute WHERE location_id IN ({placeholders}) "
            "GROUP BY location_id) latest ON latest.location_id = p.location_id "
            "AND latest.newest = p.sensing_datetime",
            matched,
        )
        readings = {
            str(row["location_id"]): SensorReading(
                str(row["location_id"]),
                float(row["total_of_directions"]),
                row["sensing_datetime"],
            )
            for row in cursor.fetchall()
            if row["total_of_directions"] is not None
        }
        score_time = now or datetime.now(MELBOURNE_TIMEZONE)
        baseline_weekday, baseline_hour = melbourne_baseline_slot(score_time)
        cursor.execute(
            "SELECT location_id, median_count, observation_count FROM baseline "
            f"WHERE location_id IN ({placeholders}) "
            "AND day_of_week = %s AND hourday = %s",
            [*matched, baseline_weekday, baseline_hour],
        )
        baselines = {
            str(row["location_id"]): SensorBaseline(
                str(row["location_id"]),
                float(row["median_count"]),
                int(row["observation_count"]),
            )
            for row in cursor.fetchall()
        }
    return score_route(matched, readings, baselines, cfg, score_time)


def main():
    """Small connection check; applications should call score_route_from_database."""
    try:
        import pymysql
    except ModuleNotFoundError:
        raise SystemExit(
            "pymysql is not installed. Run: python -m pip install -r requirements.txt"
        ) from None
    password = os.environ.get("DB_PASSWORD")
    if not password:
        password = input("Database password (visible): ").strip()
    if not password:
        raise SystemExit("Database password cannot be empty.")
    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", "tp02fit5120.c1qymwwke45u.ap-southeast-2.rds.amazonaws.com"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "admin"),
        password=password,
        database=os.environ.get("DB_NAME", "onboarding"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        config = load_config(conn)
        print(config)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
