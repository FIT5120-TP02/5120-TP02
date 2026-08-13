"""DS3 sensory scoring using hourly pedestrian counts."""

from __future__ import annotations

import math
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


# ==========================================================
# PYTHON 3.9 COMPATIBILITY
# ==========================================================

try:
    from itertools import pairwise
except ImportError:

    def pairwise(iterable):
        """Python 3.9 replacement for itertools.pairwise."""

        iterator = iter(iterable)

        try:
            previous = next(iterator)
        except StopIteration:
            return

        for current in iterator:
            yield previous, current
            previous = current


# ==========================================================
# CONSTANTS
# ==========================================================

LOW = "LOW"
HIGH = "HIGH"
NO_DATA = "NO DATA"

MELBOURNE_TIMEZONE = ZoneInfo("Australia/Melbourne")

# A sensor is HIGH when its hourly pedestrian count
# reaches or exceeds this value.
SELECTED_ABSOLUTE_THRESHOLD = 500.0

# Historical baseline must contain at least this many
# observations before it is considered reliable.
SELECTED_MIN_OBSERVATIONS = 10


# ==========================================================
# DATA CLASSES
# ==========================================================

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
    absolute_threshold: float = SELECTED_ABSOLUTE_THRESHOLD
    minimum_observations: int = SELECTED_MIN_OBSERVATIONS
    minimum_sensors: int = 1
    live_max_age_minutes: int = 90


# ==========================================================
# ROUTE SENSOR MATCHING
# ==========================================================

def _point_segment_distance_m(
    point,
    start,
    end,
):
    """
    Approximate distance from a sensor to a route segment.

    Suitable for short routes within Melbourne CBD.
    """

    reference_lat = math.radians(
        (
            point[0]
            + start[0]
            + end[0]
        )
        / 3
    )

    metres_per_degree_lat = 111_320.0

    metres_per_degree_lng = (
        metres_per_degree_lat
        * math.cos(reference_lat)
    )

    px = (
        point[1] - start[1]
    ) * metres_per_degree_lng

    py = (
        point[0] - start[0]
    ) * metres_per_degree_lat

    ex = (
        end[1] - start[1]
    ) * metres_per_degree_lng

    ey = (
        end[0] - start[0]
    ) * metres_per_degree_lat

    length_squared = (
        ex * ex
        + ey * ey
    )

    if length_squared == 0:
        return math.hypot(
            px,
            py,
        )

    projection = max(
        0.0,
        min(
            1.0,
            (
                px * ex
                + py * ey
            )
            / length_squared,
        ),
    )

    return math.hypot(
        px - projection * ex,
        py - projection * ey,
    )


def match_sensors_to_route(
    geometry: Sequence[Sequence[float]],
    sensors: Iterable[SensorLocation],
    buffer_radius_m: float = 120.0,
) -> list[str]:
    """
    Return sensors located within the route buffer.
    """

    if buffer_radius_m < 0:
        raise ValueError(
            "buffer_radius_m cannot be negative"
        )

    if len(geometry) < 2:
        return []

    points = [
        (
            float(point[0]),
            float(point[1]),
        )
        for point in geometry
    ]

    matched = []
    seen = set()

    for sensor in sensors:

        distance = min(
            _point_segment_distance_m(
                (
                    sensor.latitude,
                    sensor.longitude,
                ),
                segment_start,
                segment_end,
            )
            for segment_start, segment_end
            in pairwise(points)
        )

        if (
            distance <= buffer_radius_m
            and sensor.sensor_id not in seen
        ):
            matched.append(
                sensor.sensor_id
            )

            seen.add(
                sensor.sensor_id
            )

    return matched


# ==========================================================
# TIME HELPERS
# ==========================================================

def _is_stale(
    observed_at: datetime | None,
    now: datetime,
    max_age_minutes: int,
) -> bool:
    """Check whether a live sensor reading is too old."""

    if observed_at is None:
        return True

    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(
            tzinfo=MELBOURNE_TIMEZONE
        )

    if now.tzinfo is None:
        now = now.replace(
            tzinfo=MELBOURNE_TIMEZONE
        )

    age = (
        now.astimezone(timezone.utc)
        - observed_at.astimezone(timezone.utc)
    )

    return age > timedelta(
        minutes=max_age_minutes
    )


def melbourne_baseline_slot(
    when: datetime | None = None,
) -> tuple[int, int]:
    """
    Return Melbourne weekday and hour.

    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6
    """

    value = (
        when
        or datetime.now(
            MELBOURNE_TIMEZONE
        )
    )

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=MELBOURNE_TIMEZONE
        )
    else:
        value = value.astimezone(
            MELBOURNE_TIMEZONE
        )

    return (
        value.weekday(),
        value.hour,
    )


# ==========================================================
# LOAD CONFIGURATION
# ==========================================================

def load_config(conn) -> ScoringConfig:
    """
    Load general DS3 configuration.

    HIGH classification uses only the absolute pedestrian
    threshold of 500 pedestrians per hour.
    """

    with conn.cursor() as cursor:

        cursor.execute(
            """
            SELECT
                config_key,
                value
            FROM config
            """
        )

        values = {
            row["config_key"]: row["value"]
            for row in cursor.fetchall()
        }

    return ScoringConfig(

        buffer_radius_m=float(
            values.get(
                "route_buffer_radius_m",
                120,
            )
        ),

        absolute_threshold=float(
            values.get(
                "absolute_threshold",
                SELECTED_ABSOLUTE_THRESHOLD,
            )
        ),

        minimum_observations=int(
            values.get(
                "minimum_observations",
                SELECTED_MIN_OBSERVATIONS,
            )
        ),

        minimum_sensors=int(
            values.get(
                "minimum_route_sensors",
                1,
            )
        ),

        live_max_age_minutes=int(
            values.get(
                "live_max_age_minutes",
                90,
            )
        ),
    )


# ==========================================================
# ROUTE SCORING
# ==========================================================

def score_route(
    matched_sensor_ids: Sequence[str],
    readings: Mapping[str, SensorReading],
    baselines: Mapping[str, SensorBaseline],
    config: ScoringConfig | None = None,
    now: datetime | None = None,
) -> tuple[str, str | None]:
    """
    Score a route as HIGH, LOW or NO DATA.

    HIGH:
        At least one matched sensor has an hourly
        pedestrian count >= 500.

    LOW:
        All valid matched sensors have counts < 500.

    NO DATA:
        Required sensor or baseline data is unavailable.
    """

    cfg = config or ScoringConfig()

    sensor_ids = list(
        dict.fromkeys(
            str(sensor_id)
            for sensor_id
            in matched_sensor_ids
        )
    )

    if len(sensor_ids) < cfg.minimum_sensors:
        return (
            NO_DATA,
            None,
        )

    valid_sensor_count = 0

    for sensor_id in sensor_ids:

        reading = readings.get(
            sensor_id
        )

        baseline = baselines.get(
            sensor_id
        )

        if reading is None:
            continue

        if reading.current_count < 0:
            continue

        # Baseline is still checked for data quality,
        # but it does not determine HIGH or LOW.
        if baseline is None:
            continue

        if baseline.median_count <= 0:
            continue

        if (
            baseline.observation_count
            < cfg.minimum_observations
        ):
            continue

        valid_sensor_count += 1

        # ==================================================
        # HIGH RULE
        #
        # Only the current hourly pedestrian count matters.
        # ==================================================

        if (
            reading.current_count
            >= cfg.absolute_threshold
        ):
            return (
                HIGH,
                (
                    "This route includes a corridor "
                    "with high pedestrian density."
                ),
            )

    if valid_sensor_count < cfg.minimum_sensors:
        return (
            NO_DATA,
            None,
        )

    return (
        LOW,
        None,
    )


# ==========================================================
# SCORE ROUTE FROM DATABASE
# ==========================================================

def score_route_from_database(
    geometry: Sequence[Sequence[float]],
    conn,
    now: datetime | None = None,
) -> tuple[str, str | None]:
    """
    Match sensors to a route and score using hourly data.
    """

    cfg = load_config(
        conn
    )

    # ------------------------------------------------------
    # Load sensor locations
    # ------------------------------------------------------

    with conn.cursor() as cursor:

        cursor.execute(
            """
            SELECT
                location_id,
                latitude,
                longitude
            FROM location
            WHERE location_type = 'sensor'
            """
        )

        sensors = [
            SensorLocation(
                sensor_id=str(
                    row["location_id"]
                ),
                latitude=float(
                    row["latitude"]
                ),
                longitude=float(
                    row["longitude"]
                ),
            )
            for row in cursor.fetchall()
        ]

    matched = match_sensors_to_route(
        geometry,
        sensors,
        cfg.buffer_radius_m,
    )

    if len(matched) < cfg.minimum_sensors:
        return (
            NO_DATA,
            None,
        )

    placeholders = ", ".join(
        ["%s"] * len(matched)
    )

    score_time = (
        now
        or datetime.now(
            MELBOURNE_TIMEZONE
        )
    )

    current_hour = score_time.hour

    # ------------------------------------------------------
    # Load newest hourly record for matched sensors
    # ------------------------------------------------------

    with conn.cursor() as cursor:

        cursor.execute(
            f"""
            SELECT
                p.location_id,
                p.pedestrian_count,
                p.sensing_date,
                p.day_of_week,
                p.hourday

            FROM pedestrian_count_hour p

            JOIN (
                SELECT
                    location_id,
                    MAX(sensing_date) AS latest_date

                FROM pedestrian_count_hour

                WHERE location_id IN ({placeholders})
                  AND hourday = %s

                GROUP BY location_id
            ) latest

                ON latest.location_id = p.location_id
                AND latest.latest_date = p.sensing_date

            WHERE p.location_id IN ({placeholders})
              AND p.hourday = %s
            """,
            [
                *matched,
                current_hour,
                *matched,
                current_hour,
            ],
        )

        hourly_rows = cursor.fetchall()

        readings = {}
        baselines = {}

        for row in hourly_rows:

            sensor_id = str(
                row["location_id"]
            )

            reading_weekday = int(
                row["day_of_week"]
            )

            reading_hour = int(
                row["hourday"]
            )

            observed_at = datetime.combine(
                row["sensing_date"],
                datetime.min.time(),
            ).replace(
                hour=reading_hour,
                tzinfo=MELBOURNE_TIMEZONE,
            )

            readings[
                sensor_id
            ] = SensorReading(
                sensor_id=sensor_id,
                current_count=float(
                    row["pedestrian_count"]
                ),
                observed_at=observed_at,
            )

            cursor.execute(
                """
                SELECT
                    median_count,
                    observation_count
                FROM baseline
                WHERE location_id = %s
                  AND day_of_week = %s
                  AND hourday = %s
                """,
                (
                    int(sensor_id),
                    reading_weekday,
                    reading_hour,
                ),
            )

            baseline_row = (
                cursor.fetchone()
            )

            if baseline_row:

                baselines[
                    sensor_id
                ] = SensorBaseline(
                    sensor_id=sensor_id,
                    median_count=float(
                        baseline_row[
                            "median_count"
                        ]
                    ),
                    observation_count=int(
                        baseline_row[
                            "observation_count"
                        ]
                    ),
                )

    return score_route(
        matched,
        readings,
        baselines,
        cfg,
        score_time,
    )


# ==========================================================
# MAIN HISTORICAL SENSOR TEST
# ==========================================================

def main():
    """
    Test sensory classification using the newest available
    hourly historical record for each sensor.

    HIGH = current hourly count >= 500
    LOW  = current hourly count < 500

    Median and ratio are displayed for analysis only.
    """

    try:
        import pymysql

    except ModuleNotFoundError:

        raise SystemExit(
            "pymysql is not installed. "
            "Run: python -m pip install pymysql"
        ) from None

    # ------------------------------------------------------
    # Database connection
    # ------------------------------------------------------

    password = os.environ.get(
        "DB_PASSWORD"
    )

    if not password:

        password = input(
            "Database password (visible): "
        ).strip()

    if not password:

        raise SystemExit(
            "Database password cannot be empty."
        )

    conn = pymysql.connect(

        host=os.environ.get(
            "DB_HOST",
            (
                "tp02fit5120.c1qymwwke45u."
                "ap-southeast-2.rds.amazonaws.com"
            ),
        ),

        port=int(
            os.environ.get(
                "DB_PORT",
                "3306",
            )
        ),

        user=os.environ.get(
            "DB_USER",
            "admin",
        ),

        password=password,

        database=os.environ.get(
            "DB_NAME",
            "onboarding",
        ),

        charset="utf8mb4",

        cursorclass=(
            pymysql.cursors.DictCursor
        ),
    )

    try:

        # ==================================================
        # 1. LOAD CONFIG
        # ==================================================

        config = load_config(
            conn
        )

        print(
            "\n========================================"
        )

        print(
            "DS3 SENSORY SCORING"
        )

        print(
            "========================================"
        )

        print(
            f"\nHIGH threshold       : "
            f"{config.absolute_threshold:.0f} "
            f"pedestrians/hour"
        )

        print(
            f"Minimum observations : "
            f"{config.minimum_observations}"
        )

        print(
            "\nClassification rule:"
        )

        print(
            f"HIGH = current count >= "
            f"{config.absolute_threshold:.0f}"
        )

        print(
            f"LOW  = current count < "
            f"{config.absolute_threshold:.0f}"
        )

        # ==================================================
        # 2. GET CURRENT MELBOURNE HOUR
        # ==================================================

        now = datetime.now(
            MELBOURNE_TIMEZONE
        )

        current_hour = (
            now.hour
        )

        print(
            f"\nCurrent Melbourne time: "
            f"{now}"
        )

        print(
            f"Testing hour: "
            f"{current_hour:02d}:00"
        )

        print(
            "\nUsing newest available historical "
            "hourly record for each sensor."
        )

        # ==================================================
        # 3. LOAD NEWEST HOURLY RECORDS
        # ==================================================

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    p.location_id,

                    p.pedestrian_count
                        AS current_count,

                    p.sensing_date,

                    p.day_of_week,

                    p.hourday,

                    b.median_count,

                    b.observation_count

                FROM pedestrian_count_hour p

                JOIN (
                    SELECT
                        location_id,
                        MAX(sensing_date)
                            AS latest_date

                    FROM pedestrian_count_hour

                    WHERE hourday = %s

                    GROUP BY location_id
                ) latest

                    ON latest.location_id
                        = p.location_id

                    AND latest.latest_date
                        = p.sensing_date

                LEFT JOIN baseline b

                    ON b.location_id
                        = p.location_id

                    AND b.day_of_week
                        = p.day_of_week

                    AND b.hourday
                        = p.hourday

                WHERE p.hourday = %s

                ORDER BY p.location_id
                """,
                (
                    current_hour,
                    current_hour,
                ),
            )

            rows = (
                cursor.fetchall()
            )

        print(
            f"\nHourly sensor records loaded: "
            f"{len(rows)}"
        )

        # ==================================================
        # 4. SCORE EACH SENSOR
        # ==================================================

        high_values = []
        low_values = []
        no_data_values = []

        for row in rows:

            sensor_id = str(
                row["location_id"]
            )

            current_count = row[
                "current_count"
            ]

            median_count = row[
                "median_count"
            ]

            observation_count = row[
                "observation_count"
            ]

            # ----------------------------------------------
            # Current reading missing
            # ----------------------------------------------

            if current_count is None:

                no_data_values.append(
                    {
                        "sensor_id":
                            sensor_id,

                        "reason":
                            "Missing current reading",

                        "sensing_date":
                            row.get(
                                "sensing_date"
                            ),

                        "day_of_week":
                            row.get(
                                "day_of_week"
                            ),

                        "hourday":
                            row.get(
                                "hourday"
                            ),
                    }
                )

                continue

            current_count = float(
                current_count
            )

            # ----------------------------------------------
            # Baseline information
            #
            # Baseline does NOT control HIGH / LOW.
            # It is retained for analysis and display.
            # ----------------------------------------------

            if median_count is not None:

                median_count = float(
                    median_count
                )

            if observation_count is not None:

                observation_count = int(
                    observation_count
                )

            if (
                median_count is not None
                and median_count > 0
            ):

                ratio = (
                    current_count
                    / median_count
                )

            else:

                ratio = None

            result = {

                "sensor_id":
                    sensor_id,

                "current_count":
                    current_count,

                "median_count":
                    median_count,

                "ratio":
                    ratio,

                "observation_count":
                    observation_count,

                "sensing_date":
                    row["sensing_date"],

                "day_of_week":
                    int(
                        row["day_of_week"]
                    ),

                "hourday":
                    int(
                        row["hourday"]
                    ),
            }

            # ==================================================
            # NEW HIGH / LOW RULE
            #
            # HIGH if current hourly count >= 500.
            #
            # LOW if current hourly count < 500.
            #
            # Median and ratio do NOT affect classification.
            # ==================================================

            if (
                current_count
                >= config.absolute_threshold
            ):

                high_values.append(
                    result
                )

            else:

                low_values.append(
                    result
                )

        # ==================================================
        # PRINT FUNCTION
        # ==================================================

        def print_sensor(row):

            median_text = (
                f"{row['median_count']:.1f}"
                if row["median_count"] is not None
                else "N/A"
            )

            ratio_text = (
                f"{row['ratio']:.2f}"
                if row["ratio"] is not None
                else "N/A"
            )

            observations_text = (
                str(
                    row["observation_count"]
                )
                if row["observation_count"] is not None
                else "N/A"
            )

            print(
                f"Sensor {row['sensor_id']} | "
                f"Current: "
                f"{row['current_count']:.0f} | "
                f"Median: "
                f"{median_text} | "
                f"Ratio: "
                f"{ratio_text} | "
                f"Date: "
                f"{row['sensing_date']} | "
                f"Weekday: "
                f"{row['day_of_week']} | "
                f"Hour: "
                f"{row['hourday']:02d}:00 | "
                f"Observations: "
                f"{observations_text}"
            )

        # ==================================================
        # 5. HIGH VALUES
        # ==================================================

        print(
            "\n========================================"
        )

        print(
            "HIGH VALUES"
        )

        print(
            "========================================"
        )

        if not high_values:

            print(
                "No HIGH sensors found."
            )

        else:

            for row in high_values:

                print_sensor(
                    row
                )

        # ==================================================
        # 6. LOW VALUES
        # ==================================================

        print(
            "\n========================================"
        )

        print(
            "LOW VALUES"
        )

        print(
            "========================================"
        )

        if not low_values:

            print(
                "No LOW sensors found."
            )

        else:

            for row in low_values:

                print_sensor(
                    row
                )

        # ==================================================
        # 7. NO DATA
        # ==================================================

        print(
            "\n========================================"
        )

        print(
            "NO DATA"
        )

        print(
            "========================================"
        )

        if not no_data_values:

            print(
                "No missing sensor readings."
            )

        else:

            for row in no_data_values:

                print(
                    f"Sensor "
                    f"{row['sensor_id']} | "
                    f"Reason: "
                    f"{row['reason']} | "
                    f"Date: "
                    f"{row['sensing_date']} | "
                    f"Weekday: "
                    f"{row['day_of_week']} | "
                    f"Hour: "
                    f"{row['hourday']}"
                )

        # ==================================================
        # 8. SUMMARY
        # ==================================================

        print(
            "\n========================================"
        )

        print(
            "SUMMARY"
        )

        print(
            "========================================"
        )

        print(
            f"HIGH    : "
            f"{len(high_values)}"
        )

        print(
            f"LOW     : "
            f"{len(low_values)}"
        )

        print(
            f"NO DATA : "
            f"{len(no_data_values)}"
        )

        print(
            f"TOTAL   : "
            f"{len(rows)}"
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()