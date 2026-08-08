"""Smoke tests for the REST API surface (integration-level, not unit)."""


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_login_and_read_own_preferences(client):
    register = client.post(
        "/api/auth/register", json={"username": "freddy", "password": "commute123"}
    )
    assert register.status_code == 201

    login = client.post("/api/auth/login", data={"username": "freddy", "password": "commute123"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "freddy"

    prefs = client.get("/api/users/me/preferences", headers=headers)
    assert prefs.status_code == 200


def test_cannot_read_preferences_without_token(client):
    response = client.get("/api/users/me/preferences")
    assert response.status_code == 401


def test_compare_routes_returns_low_high_and_no_data(client):
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
    statuses = {r["sensory_status"] for r in routes}
    # Mirrors the Prototype slide: one LOW, one HIGH, one NO DATA
    assert statuses == {"LOW", "HIGH", "NO DATA"}


def test_refuges_fixture_list(client):
    response = client.get("/api/refuges", params={"lat": -37.8102, "lng": 144.9628})
    assert response.status_code == 200
    body = response.json()
    assert len(body["refuges"]) >= 1
    assert all("category" in r for r in body["refuges"])


def test_register_rejects_password_over_72_bytes(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "toolong", "password": "a" * 73},
    )
    assert response.status_code == 422


def test_login_with_over_72_byte_password_is_unauthorized_not_500(client):
    client.post("/api/auth/register", json={"username": "freddy2", "password": "commute123"})
    response = client.post("/api/auth/login", data={"username": "freddy2", "password": "a" * 73})
    assert response.status_code == 401


def test_refuges_returns_empty_list_when_nothing_within_radius(client):
    # Melbourne CBD fixtures are nowhere near this point (middle of the
    # Pacific Ocean) - a tiny radius here must return [], not silently
    # fall back to every fixture regardless of distance.
    response = client.get("/api/refuges", params={"lat": 0.0, "lng": -160.0, "radius_km": 1.5})
    assert response.status_code == 200
    assert response.json()["refuges"] == []
