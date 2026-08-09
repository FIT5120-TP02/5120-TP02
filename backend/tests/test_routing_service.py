"""
Tests for app/services/routing_service.py's OpenRouteService integration.

No real network calls here - httpx.post is monkeypatched with a fixture
response shaped like ORS's actual geojson output, so these run offline
like the rest of the suite.
"""

import pytest

from app.core.config import get_settings
from app.services import routing_service


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


_ORS_GEOJSON_FIXTURE = {
    "features": [
        {
            "properties": {"summary": {"distance": 1400.0, "duration": 1080.0}},
            "geometry": {
                "coordinates": [
                    [144.9631, -37.8136],
                    [144.9628, -37.8102],
                ]
            },
        },
        {
            "properties": {"summary": {"distance": 900.0, "duration": 720.0}},
            "geometry": {
                "coordinates": [
                    [144.9631, -37.8136],
                    [144.9628, -37.8102],
                ]
            },
        },
    ]
}


def test_ors_candidate_routes_parses_geojson_response(monkeypatch):
    monkeypatch.setenv("ROUTING_PROVIDER", "openrouteservice")
    monkeypatch.setenv("ROUTING_SERVICE_API_KEY", "fake-key-for-test")
    get_settings.cache_clear()

    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: _FakeResponse(_ORS_GEOJSON_FIXTURE))

    routes = routing_service.get_candidate_routes(-37.8136, 144.9631, -37.8102, 144.9628)

    assert len(routes) == 2
    assert routes[0].distance_km == 1.4
    assert routes[0].duration_min == 18.0
    # geometry is converted from ORS's [lng, lat] to this API's [lat, lng]
    assert routes[0].geometry[0] == [-37.8136, 144.9631]

    get_settings.cache_clear()


def test_ors_candidate_routes_requires_api_key(monkeypatch):
    monkeypatch.setenv("ROUTING_PROVIDER", "openrouteservice")
    # Explicitly set to "" rather than delenv - pydantic-settings falls
    # back to reading a real on-disk .env when the env var is merely
    # unset, and a dev machine's .env may have a real key already filled
    # in (same class of bug as the JWT secret test). An explicit empty
    # string is a real env var value, so it takes precedence and the test
    # passes for the right reason regardless of what's in .env locally.
    monkeypatch.setenv("ROUTING_SERVICE_API_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="ROUTING_SERVICE_API_KEY is not set"):
        routing_service.get_candidate_routes(-37.8136, 144.9631, -37.8102, 144.9628)

    get_settings.cache_clear()
