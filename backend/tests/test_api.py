"""Smoke tests for the REST API surface (integration-level, not unit).

No account/login tests here - the product has no auth system (team
decision: removed for privacy, per tutor's guidance). Every endpoint is
public/anonymous.

Sensor-matching logic (LOW/HIGH/NO DATA over real data) is unit-tested
separately in test_route_sensor_matching.py, since coupling it to the
`mock` routing provider's fixed fixture geometry here would be brittle.
"""

from datetime import datetime, timezone

from app.models import Location, SensoryReadingRecord
from app.routers.routes import _latest_readings


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_compare_routes_returns_three_routes_with_valid_statuses(client):
    response = client.post(
        "/api/routes/compare",
        json={
            "origin_lat": -37.8136,
            "origin_lng": 144.9631,
            "destination_lat": -37.8102,
            "destination_lng": 144.9628,
        },
    )
    assert response.status_code == 200
    routes = response.json()["routes"]
    assert len(routes) == 3
    assert all(r["sensory_status"] in {"LOW", "HIGH", "NO DATA"} for r in routes)


def test_latest_readings_uses_pr14_sensory_table_for_low_and_high(db_session):
    observed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add_all(
        [
            SensoryReadingRecord(
                location_id=901,
                window_end=observed_at,
                pedestrian_count=120,
                sensory_status="Low",
            ),
            SensoryReadingRecord(
                location_id=902,
                window_end=observed_at,
                pedestrian_count=850,
                sensory_status="High",
            ),
            SensoryReadingRecord(
                location_id=903,
                window_end=observed_at,
                pedestrian_count=None,
                sensory_status="No Data",
            ),
        ]
    )
    db_session.commit()

    readings = _latest_readings(db_session, [901, 902, 903])

    assert readings["901"].current_count == 120
    assert readings["902"].current_count == 850
    assert "903" not in readings


def test_refuges_returns_seeded_location_within_radius(client, db_session):
    db_session.add(
        Location(
            location_id=101,
            location_name="Test Library",
            latitude=-37.8102,
            longitude=144.9628,
            location_type="refuge",
            category="Library",
        )
    )
    db_session.commit()

    response = client.get("/api/refuges", params={"lat": -37.8102, "lng": 144.9628})
    assert response.status_code == 200
    refuges = response.json()["refuges"]
    matched = next(r for r in refuges if r["location_id"] == 101)
    assert matched["category"] == "Library"


def test_refuges_returns_empty_list_when_nothing_within_radius(client):
    # Middle of the Pacific Ocean - guaranteed nothing seeded anywhere
    # else in the test DB is within 1.5km of this, regardless of what
    # other tests inserted.
    response = client.get("/api/refuges", params={"lat": 0.0, "lng": -160.0, "radius_km": 1.5})
    assert response.status_code == 200
    assert response.json()["refuges"] == []


def test_refuges_rejects_zero_walking_speed(client):
    # walking_speed_kmh=0 would divide-by-zero computing eta_min - must be
    # rejected by request validation, not reach the handler at all.
    response = client.get(
        "/api/refuges",
        params={"lat": -37.8102, "lng": 144.9628, "walking_speed_kmh": 0},
    )
    assert response.status_code == 422


def test_refuges_rejects_negative_radius(client):
    response = client.get(
        "/api/refuges",
        params={"lat": -37.8102, "lng": 144.9628, "radius_km": -1},
    )
    assert response.status_code == 422


def test_refuges_rejects_excessive_radius(client):
    response = client.get(
        "/api/refuges",
        params={"lat": -37.8102, "lng": 144.9628, "radius_km": 999},
    )
    assert response.status_code == 422
