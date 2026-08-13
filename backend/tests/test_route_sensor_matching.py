"""
Tests for the SQLAlchemy glue in app/routers/routes.py
(_sensor_locations, _latest_readings, _baselines_for_slot) that feeds
DS3's approved sensory_scoring functions (match_sensors_to_route,
score_route) with real data from the shared DB schema.

DS3's own matching/scoring algorithms are tested directly in
test_sensory_scoring.py (ported from their test suite) - these tests
only cover the glue: does the right SQLAlchemy data turn into the right
SensorLocation/SensorReading/SensorBaseline objects.
"""

from datetime import datetime, timedelta, timezone

from app.models import Address, Baseline, Location, PedestrianCountMinute
from app.routers.routes import (
    _baselines_for_slot,
    _latest_readings,
    _nearest_address,
    _representative_sensor,
    _sensor_locations,
)
from app.services.sensory_scoring import (
    HIGH,
    LOW,
    NO_DATA,
    ScoringConfig,
    SensorBaseline,
    SensorReading,
    match_sensors_to_route,
)


def test_sensor_locations_only_returns_sensor_type_rows(db_session):
    db_session.add_all(
        [
            Location(
                location_id=9001,
                location_name="A sensor",
                latitude=-37.81,
                longitude=144.96,
                location_type="sensor",
                placement="Outdoor",
            ),
            Location(
                location_id=9002,
                location_name="A refuge",
                latitude=-37.81,
                longitude=144.96,
                location_type="refuge",
                category="Park",
            ),
        ]
    )
    db_session.commit()

    sensors = _sensor_locations(db_session)
    sensor_ids = {s.sensor_id for s in sensors}

    assert "9001" in sensor_ids
    assert "9002" not in sensor_ids


def test_sensor_locations_excludes_indoor_placement(db_session):
    # Confirmed against the live DB on 2026-08-11: all 34 Indoor sensors
    # (libraries, community hubs, visitor centres) have zero rows in
    # pedestrian_count_minute/_hour/baseline - Melbourne's public counting
    # datasets only cover outdoor street-level sensors. Matching one of
    # these "ghost" sensors used to permanently stick a route's
    # sensory_status at NO DATA via score_route()'s all-matched-sensors
    # rule, even when every real outdoor sensor nearby was fine.
    db_session.add_all(
        [
            Location(
                location_id=9003,
                location_name="An outdoor sensor",
                latitude=-37.81,
                longitude=144.96,
                location_type="sensor",
                placement="Outdoor",
            ),
            Location(
                location_id=9004,
                location_name="An indoor sensor (never reports data)",
                latitude=-37.81,
                longitude=144.96,
                location_type="sensor",
                placement="Indoor",
            ),
        ]
    )
    db_session.commit()

    sensors = _sensor_locations(db_session)
    sensor_ids = {s.sensor_id for s in sensors}

    assert "9003" in sensor_ids
    assert "9004" not in sensor_ids


def test_latest_readings_picks_the_most_recent_row_per_location(db_session):
    now = datetime(2026, 8, 9, 3, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    db_session.add_all(
        [
            PedestrianCountMinute(
                location_id=9101,
                sensing_datetime=now - timedelta(minutes=10),
                sensing_date=(now - timedelta(minutes=10)).date(),
                sensing_time=(now - timedelta(minutes=10)).time(),
                total_of_directions=10,
            ),
            PedestrianCountMinute(
                location_id=9101,
                sensing_datetime=now,
                sensing_date=now.date(),
                sensing_time=now.time(),
                total_of_directions=99,  # this is the most recent - should win
            ),
        ]
    )
    db_session.commit()

    readings = _latest_readings(db_session, [9101])

    assert readings["9101"].current_count == 99
    assert readings["9101"].observed_at == now


def test_latest_readings_skips_rows_with_no_count(db_session):
    now = datetime(2026, 8, 9, 3, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    db_session.add(
        PedestrianCountMinute(
            location_id=9102,
            sensing_datetime=now,
            sensing_date=now.date(),
            sensing_time=now.time(),
            total_of_directions=None,
        )
    )
    db_session.commit()

    readings = _latest_readings(db_session, [9102])

    assert "9102" not in readings


def test_baselines_for_slot_filters_by_day_and_hour(db_session):
    db_session.add_all(
        [
            Baseline(
                location_id=9201,
                day_of_week=1,
                hourday=14,
                average_count=50,
                median_count=50,
                observation_count=20,
                recomputed_at=datetime(2026, 8, 1, 0, 0),
            ),
            Baseline(
                location_id=9201,
                day_of_week=1,
                hourday=15,  # different hour - must not match
                average_count=999,
                median_count=999,
                observation_count=20,
                recomputed_at=datetime(2026, 8, 1, 0, 0),
            ),
        ]
    )
    db_session.commit()

    baselines = _baselines_for_slot(db_session, [9201], day_of_week=1, hourday=14)

    assert baselines["9201"].median_count == 50


def test_match_sensors_to_route_still_wired_through_correctly(db_session):
    # Sanity check that the glue passes real SensorLocation objects into
    # DS3's match_sensors_to_route() correctly end-to-end (not testing
    # the matching algorithm itself - that's DS3's, tested separately).
    db_session.add(
        Location(
            location_id=9301,
            location_name="On the route",
            latitude=-37.8100,
            longitude=144.9600,
            location_type="sensor",
            placement="Outdoor",
        )
    )
    db_session.commit()

    sensors = _sensor_locations(db_session)
    matched = match_sensors_to_route(
        [[-37.8100, 144.9600], [-37.8101, 144.9601]], sensors, buffer_radius_m=120
    )

    assert "9301" in matched


class TestRepresentativeSensor:
    """
    Tests for `_representative_sensor` (routes.py) - review round 5
    feedback: (1) NO DATA must not leak a representative sensor even when
    some matched sensor happens to have a reading, and (2) the HIGH
    representative must be one of the sensors that actually satisfies
    score_route's both-conditions rule, not just whichever has the
    largest raw current_count.
    """

    def test_none_for_no_data_even_when_a_matched_sensor_has_a_reading(self):
        # "1" has a live reading but no baseline at all - this is exactly
        # the kind of matched-sensor set that makes score_route() return
        # NO DATA overall (another matched sensor might be missing data),
        # so the representative selection must key off the *status*
        # score_route already computed, not re-derive its own, looser
        # condition from `readings` alone.
        readings = {"1": SensorReading("1", 900, datetime(2026, 8, 9, tzinfo=timezone.utc))}
        baselines: dict = {}
        config = ScoringConfig()

        assert _representative_sensor(NO_DATA, ["1"], readings, baselines, config) is None

    def test_none_when_no_sensors_matched(self):
        config = ScoringConfig()
        assert _representative_sensor(LOW, [], {}, {}, config) is None

    def test_high_picks_the_sensor_satisfying_both_conditions_not_the_largest_raw_count(self):
        now = datetime(2026, 8, 9, tzinfo=timezone.utc)
        config = ScoringConfig()  # absolute_threshold=500, relative_threshold=1.5

        readings = {
            "big_raw_not_high": SensorReading("big_raw_not_high", 1000, now),
            "smaller_raw_is_high": SensorReading("smaller_raw_is_high", 600, now),
        }
        baselines = {
            # 1000 < 900 * 1.5 (1350) -> fails the relative condition,
            # despite having the largest raw reading of the two.
            "big_raw_not_high": SensorBaseline("big_raw_not_high", 900, 20),
            # 600 >= 500 (absolute) and 600 >= 50 * 1.5 (75) (relative) -
            # satisfies both HIGH conditions.
            "smaller_raw_is_high": SensorBaseline("smaller_raw_is_high", 50, 20),
        }

        representative = _representative_sensor(HIGH, list(readings), readings, baselines, config)

        assert representative == "smaller_raw_is_high"

    def test_low_uses_ratio_to_baseline_not_raw_count(self):
        now = datetime(2026, 8, 9, tzinfo=timezone.utc)
        config = ScoringConfig()

        readings = {
            "bigger_raw_lower_ratio": SensorReading("bigger_raw_lower_ratio", 80, now),
            "smaller_raw_higher_ratio": SensorReading("smaller_raw_higher_ratio", 50, now),
        }
        baselines = {
            # ratio 80 / 100 = 0.8
            "bigger_raw_lower_ratio": SensorBaseline("bigger_raw_lower_ratio", 100, 20),
            # ratio 50 / 20 = 2.5 - closest to tipping into HIGH even though
            # its raw count is smaller than the other sensor's.
            "smaller_raw_higher_ratio": SensorBaseline("smaller_raw_higher_ratio", 20, 20),
        }

        representative = _representative_sensor(LOW, list(readings), readings, baselines, config)

        assert representative == "smaller_raw_higher_ratio"


class TestNearestAddress:
    """
    Tests for `_nearest_address` (routes.py) - looks up DS's separate
    `address` table (~50k real Melbourne addresses), NOT `location.address`
    (that column exists but has never been populated for any row).
    """

    def test_picks_the_closer_of_two_candidates_in_the_bounding_box(self, db_session):
        query_lat, query_lng = -38.0000, 145.2000
        db_session.add_all(
            [
                Address(
                    address_id=90001,
                    address_pnt="1 Nearby St, Melbourne",
                    latitude=-38.0001,  # ~11m away
                    longitude=145.2000,
                ),
                Address(
                    address_id=90002,
                    address_pnt="2 Farther Ave, Melbourne",
                    latitude=-38.0050,  # ~555m away
                    longitude=145.2000,
                ),
            ]
        )
        db_session.commit()

        result = _nearest_address(db_session, query_lat, query_lng)

        assert result == "1 Nearby St, Melbourne"

    def test_returns_none_when_nothing_in_the_bounding_box(self, db_session):
        # Middle of the Pacific Ocean - guaranteed nothing seeded anywhere
        # else is within the search box of this.
        result = _nearest_address(db_session, 0.0, -160.0)

        assert result is None
