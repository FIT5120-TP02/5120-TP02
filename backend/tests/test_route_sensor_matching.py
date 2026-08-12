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

from app.models import Baseline, Location, PedestrianCountMinute
from app.routers.routes import _baselines_for_slot, _latest_readings, _sensor_locations
from app.services.sensory_scoring import match_sensors_to_route


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
