"""
Tests for the real sensor-matching logic in app/routers/routes.py
(_match_sensors_to_route, _real_sensor_data_for) - the code that replaced
the old fixture placeholder once the real `location`/`baseline`/
`pedestrian_count_minute` schema was confirmed against the live DB.

These call the helpers directly rather than going through
POST /api/routes/compare, so they don't depend on the mock routing
provider's fixed fixture geometry - full control over coordinates here.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.models import Baseline, Location, PedestrianCountMinute
from app.routers.routes import _match_sensors_to_route, _real_sensor_data_for


def _now_local():
    return datetime.now(ZoneInfo(get_settings().local_timezone))


def test_match_sensors_to_route_includes_within_radius_excludes_outside(db_session):
    db_session.add_all(
        [
            Location(
                location_id=8001,
                location_name="On route",
                latitude=-37.8100,
                longitude=144.9600,
                location_type="sensor",
            ),
            Location(
                location_id=8002,
                location_name="Far from route",
                latitude=-37.8200,  # ~1.1km away - outside the 0.1km default radius
                longitude=144.9600,
                location_type="sensor",
            ),
        ]
    )
    db_session.commit()

    geometry = [[-37.8100, 144.9600], [-37.8095, 144.9605]]
    matched = _match_sensors_to_route(db_session, geometry)

    matched_ids = {s.location_id for s in matched}
    assert 8001 in matched_ids
    assert 8002 not in matched_ids


def test_real_sensor_data_for_attaches_reading_and_baseline(db_session):
    now = _now_local()
    sensor = Location(
        location_id=8101,
        location_name="Test sensor",
        latitude=-37.81,
        longitude=144.96,
        location_type="sensor",
    )
    db_session.add(sensor)
    db_session.add(
        Baseline(
            location_id=8101,
            day_of_week=now.weekday(),
            hourday=now.hour,
            average_count=60,
            median_count=60,
            observation_count=30,
            recomputed_at=now.replace(tzinfo=None, microsecond=0),
        )
    )
    db_session.add(
        PedestrianCountMinute(
            location_id=8101,
            sensing_datetime=now.replace(tzinfo=None, microsecond=0),
            sensing_date=now.date(),
            sensing_time=now.time().replace(microsecond=0),
            total_of_directions=40,
        )
    )
    db_session.commit()

    matched_ids, readings, baselines = _real_sensor_data_for(db_session, [sensor])

    assert matched_ids == ["8101"]
    assert readings["8101"].current_count == 40
    assert baselines["8101"].median_count == 60
    assert baselines["8101"].observation_count == 30


def test_real_sensor_data_for_skips_sensor_with_no_reading(db_session):
    now = _now_local()
    sensor = Location(
        location_id=8102,
        location_name="No reading sensor",
        latitude=-37.81,
        longitude=144.96,
        location_type="sensor",
    )
    db_session.add(sensor)
    db_session.add(
        Baseline(
            location_id=8102,
            day_of_week=now.weekday(),
            hourday=now.hour,
            average_count=60,
            median_count=60,
            observation_count=30,
            recomputed_at=now.replace(tzinfo=None, microsecond=0),
        )
    )
    db_session.commit()

    matched_ids, readings, baselines = _real_sensor_data_for(db_session, [sensor])

    assert matched_ids == ["8102"]
    assert "8102" not in readings
    assert "8102" in baselines
