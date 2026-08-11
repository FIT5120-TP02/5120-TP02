"""DS3 sensory scoring using the tables produced by DS1 and DS2."""

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
    reliable baseline. HIGH requires both DS2's absolute and relative limits.
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

    high_sensor_ids = [
        sensor_id
        for sensor_id in sensor_ids
        if readings[sensor_id].current_count >= cfg.absolute_threshold
        and readings[sensor_id].current_count
        >= baselines[sensor_id].median_count * cfg.relative_threshold
    ]
    if high_sensor_ids:
        return (
            HIGH,
            "This route includes a corridor with unusually high pedestrian density.",
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
        minimum_observations=int(values.get("minimum_observations", 10)),
        minimum_sensors=int(values.get("minimum_route_sensors", 1)),
        live_max_age_minutes=int(values.get("live_max_age_minutes", 30)),
    )


def _sensor_readings_from_sensory_rows(
    rows,
) -> tuple[dict[str, SensorReading], set[str]]:
    """Convert DS1's sensory_reading rows without trusting invalid NULL counts."""
    covered_sensor_ids = {str(row["location_id"]) for row in rows}
    readings = {
        str(row["location_id"]): SensorReading(
            str(row["location_id"]),
            float(row["pedestrian_count"]),
            row["window_end"],
        )
        for row in rows
        if str(row["sensory_status"]).upper() in {LOW, HIGH}
        and row["pedestrian_count"] is not None
        and row["pedestrian_count"] >= 0
    }
    return readings, covered_sensor_ids


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
            "SELECT sr.location_id, sr.pedestrian_count, sr.window_end, "
            "sr.sensory_status FROM sensory_reading sr JOIN ("
            "SELECT location_id, MAX(window_end) AS newest "
            f"FROM sensory_reading WHERE location_id IN ({placeholders}) "
            "GROUP BY location_id) latest ON latest.location_id = sr.location_id "
            "AND latest.newest = sr.window_end",
            matched,
        )
        readings, covered_sensor_ids = _sensor_readings_from_sensory_rows(cursor.fetchall())

        fallback_ids = [sensor_id for sensor_id in matched if sensor_id not in covered_sensor_ids]
        if fallback_ids:
            fallback_placeholders = ", ".join(["%s"] * len(fallback_ids))
            cursor.execute(
                "SELECT p.location_id, p.total_of_directions, p.sensing_datetime "
                "FROM pedestrian_count_minute p JOIN ("
                "SELECT location_id, MAX(sensing_datetime) AS newest "
                "FROM pedestrian_count_minute "
                f"WHERE location_id IN ({fallback_placeholders}) "
                "GROUP BY location_id) latest ON latest.location_id = p.location_id "
                "AND latest.newest = p.sensing_datetime",
                fallback_ids,
            )
            readings.update(
                {
                    str(row["location_id"]): SensorReading(
                        str(row["location_id"]),
                        float(row["total_of_directions"]),
                        row["sensing_datetime"],
                    )
                    for row in cursor.fetchall()
                    if row["total_of_directions"] is not None
                }
            )

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
