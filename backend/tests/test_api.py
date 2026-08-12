"""Smoke tests for the REST API surface (integration-level, not unit).

No account/login tests here - the product has no auth system (team
decision: removed for privacy, per tutor's guidance). Every endpoint is
public/anonymous.

Sensor-matching logic (LOW/HIGH/NO DATA over real data) is unit-tested
separately in test_route_sensor_matching.py, since coupling it to the
`mock` routing provider's fixed fixture geometry here would be brittle.
"""

from datetime import datetime, timezone

from app.models import Address, Baseline, Location, PedestrianCountHour, PedestrianCountMinute
from app.services.sensory_scoring import melbourne_baseline_slot


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


# ---------- sensory_value / address_pnt / pedestrian_per_min / pedestrian_per_hour ----------
# Review round 5 feedback: endpoint-level coverage for HIGH, LOW, NO DATA,
# and a multi-sensor case (unit tests for the selection logic itself live in
# test_route_sensor_matching.py::TestRepresentativeSensor).
#
# Each test uses its own, non-overlapping patch of coordinates (well away
# from other test files' fixtures and from each other) since the sqlite test
# database is a single in-memory instance shared for the whole test session.


def _seed_sensor(
    db_session,
    location_id,
    lat,
    lng,
    *,
    name="Test sensor",
    address=None,
    current_count=None,
    sensing_dt=None,
    baseline_median=None,
    baseline_observations=20,
    day_of_week=None,
    hourday=None,
    hourly_count=None,
):
    """Seed one Outdoor sensor location, with optional live reading/baseline/
    hourly-aggregate rows attached (all three are None by default, i.e.
    "sensor exists but has never reported"). `address`, if given, seeds a
    matching row in the separate `address` table at the same lat/lng
    (address_pnt's real source - not location.address, which is never
    populated - see _nearest_address in app/routers/routes.py)."""
    db_session.add(
        Location(
            location_id=location_id,
            location_name=name,
            latitude=lat,
            longitude=lng,
            location_type="sensor",
            placement="Outdoor",
        )
    )
    if address is not None:
        db_session.add(
            Address(
                address_id=location_id * 10,
                address_pnt=address,
                latitude=lat,
                longitude=lng,
            )
        )
    if current_count is not None:
        dt = sensing_dt or datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add(
            PedestrianCountMinute(
                location_id=location_id,
                sensing_datetime=dt,
                sensing_date=dt.date(),
                sensing_time=dt.time(),
                total_of_directions=current_count,
            )
        )
    if baseline_median is not None:
        db_session.add(
            Baseline(
                location_id=location_id,
                day_of_week=day_of_week,
                hourday=hourday,
                average_count=baseline_median,
                median_count=baseline_median,
                observation_count=baseline_observations,
                recomputed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
    if hourly_count is not None:
        db_session.add(
            PedestrianCountHour(
                id=location_id * 1000,
                location_id=location_id,
                sensing_date=datetime.now(timezone.utc).date(),
                day_of_week=day_of_week if day_of_week is not None else 0,
                hourday=hourday if hourday is not None else 0,
                pedestrian_count=hourly_count,
            )
        )
    db_session.commit()


def test_compare_routes_no_data_route_has_null_sensory_fields(client, db_session):
    lat, lng = -37.9500, 145.1000
    _seed_sensor(db_session, 9401, lat, lng)  # never reported -> NO DATA

    response = client.post(
        "/api/routes/compare",
        json={
            "origin_lat": lat,
            "origin_lng": lng,
            "destination_lat": lat + 0.001,
            "destination_lng": lng + 0.001,
        },
    )
    assert response.status_code == 200
    routes = response.json()["routes"]
    assert routes
    for route in routes:
        assert route["sensory_status"] == "NO DATA"
        assert route["sensory_value"] is None
        assert route["address_pnt"] is None
        assert route["pedestrian_per_min"] is None
        assert route["pedestrian_per_hour"] is None


def test_compare_routes_low_status_picks_sensor_with_highest_ratio_to_baseline(client, db_session):
    lat, lng = -37.9600, 145.1100
    now = datetime.now(timezone.utc)
    day_of_week, hourday = melbourne_baseline_slot(now)
    sensing_dt = now.replace(tzinfo=None)

    # Both sensors sit within the default 120m buffer of the route's origin
    # and both stay well under the absolute HIGH threshold (500), so the
    # route is guaranteed LOW - but their ratios to baseline differ, and the
    # higher-ratio one (sensor B) must be the one surfaced, not sensor A
    # even though nothing here depends on raw magnitude.
    _seed_sensor(
        db_session,
        9402,
        lat,
        lng,
        name="Sensor A (lower ratio)",
        current_count=80,
        sensing_dt=sensing_dt,
        baseline_median=100,  # ratio 0.8
        day_of_week=day_of_week,
        hourday=hourday,
        hourly_count=8,
    )
    _seed_sensor(
        db_session,
        9403,
        lat + 0.00005,
        lng + 0.00005,
        name="Sensor B (higher ratio)",
        address="23 Mackenzie St, Melbourne",
        current_count=50,
        sensing_dt=sensing_dt,
        baseline_median=20,  # ratio 2.5
        day_of_week=day_of_week,
        hourday=hourday,
        hourly_count=15,
    )

    response = client.post(
        "/api/routes/compare",
        json={
            "origin_lat": lat,
            "origin_lng": lng,
            "destination_lat": lat + 0.001,
            "destination_lng": lng + 0.001,
        },
    )
    assert response.status_code == 200
    routes = response.json()["routes"]
    assert routes
    for route in routes:
        assert route["sensory_status"] == "LOW"
        assert route["sensory_value"] == 50
        assert route["pedestrian_per_min"] == 50
        assert route["pedestrian_per_hour"] == 15
        assert route["address_pnt"] == "23 Mackenzie St, Melbourne"


def test_compare_routes_high_status_picks_sensor_satisfying_both_conditions(client, db_session):
    lat, lng = -37.9700, 145.1200
    now = datetime.now(timezone.utc)
    day_of_week, hourday = melbourne_baseline_slot(now)
    sensing_dt = now.replace(tzinfo=None)

    # Sensor A has the bigger raw reading but fails the *relative* HIGH
    # condition (1000 < 900 * 1.5 = 1350). Sensor B has a smaller raw
    # reading but satisfies both HIGH conditions (600 >= 500 absolute,
    # 600 >= 50 * 1.5 = 75 relative) - B must be the one surfaced, not A.
    _seed_sensor(
        db_session,
        9404,
        lat,
        lng,
        name="Sensor A (big raw, not HIGH)",
        current_count=1000,
        sensing_dt=sensing_dt,
        baseline_median=900,
        day_of_week=day_of_week,
        hourday=hourday,
    )
    _seed_sensor(
        db_session,
        9405,
        lat + 0.00005,
        lng + 0.00005,
        name="Sensor B (smaller raw, is HIGH)",
        address="88 Little Bourke St, Melbourne",
        current_count=600,
        sensing_dt=sensing_dt,
        baseline_median=50,
        day_of_week=day_of_week,
        hourday=hourday,
    )

    response = client.post(
        "/api/routes/compare",
        json={
            "origin_lat": lat,
            "origin_lng": lng,
            "destination_lat": lat + 0.001,
            "destination_lng": lng + 0.001,
        },
    )
    assert response.status_code == 200
    routes = response.json()["routes"]
    assert routes
    for route in routes:
        assert route["sensory_status"] == "HIGH"
        assert route["sensory_value"] == 600
        assert route["pedestrian_per_min"] == 600
        assert route["address_pnt"] == "88 Little Bourke St, Melbourne"


def test_compare_routes_multi_sensor_route_fields_match_the_picked_sensor(client, db_session):
    """Three matched sensors - the representative's fields must not get
    mixed up with either of the other two matched sensors' data."""
    lat, lng = -37.9800, 145.1300
    now = datetime.now(timezone.utc)
    day_of_week, hourday = melbourne_baseline_slot(now)
    sensing_dt = now.replace(tzinfo=None)

    _seed_sensor(
        db_session,
        9406,
        lat,
        lng,
        name="Sensor 1",
        current_count=30,
        sensing_dt=sensing_dt,
        baseline_median=100,  # ratio 0.3
        day_of_week=day_of_week,
        hourday=hourday,
        hourly_count=3,
    )
    _seed_sensor(
        db_session,
        9407,
        lat + 0.00005,
        lng,
        name="Sensor 2 (should be picked - highest ratio)",
        address="10 Flinders Ln, Melbourne",
        current_count=60,
        sensing_dt=sensing_dt,
        baseline_median=40,  # ratio 1.5
        day_of_week=day_of_week,
        hourday=hourday,
        hourly_count=6,
    )
    _seed_sensor(
        db_session,
        9408,
        lat,
        lng + 0.00005,
        name="Sensor 3",
        current_count=45,
        sensing_dt=sensing_dt,
        baseline_median=90,  # ratio 0.5
        day_of_week=day_of_week,
        hourday=hourday,
        hourly_count=4,
    )

    response = client.post(
        "/api/routes/compare",
        json={
            "origin_lat": lat,
            "origin_lng": lng,
            "destination_lat": lat + 0.001,
            "destination_lng": lng + 0.001,
        },
    )
    assert response.status_code == 200
    routes = response.json()["routes"]
    assert routes
    for route in routes:
        assert route["sensory_status"] == "LOW"
        assert route["sensory_value"] == 60
        assert route["pedestrian_per_min"] == 60
        assert route["pedestrian_per_hour"] == 6
        assert route["address_pnt"] == "10 Flinders Ln, Melbourne"
