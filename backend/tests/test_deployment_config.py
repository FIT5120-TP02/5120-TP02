"""
Regression test for review round 3, issue #5: a real deployment left with
ROUTING_PROVIDER=mock (e.g. because only .env.example was copied, which
intentionally defaults to mock for local dev) would silently keep serving
fixture routes - the API still returns 200s, so nothing about the
response itself flags it. app/main.py::lifespan logs a warning in this
case; this test makes sure that warning actually fires rather than
relying on a human reading Render's logs.
"""

import logging

from fastapi.testclient import TestClient

from app.main import app


def test_logs_warning_when_routing_provider_is_mock_at_startup(caplog):
    with caplog.at_level(logging.WARNING, logger="app.startup"):
        with TestClient(app):
            pass

    assert any("ROUTING_PROVIDER=mock" in record.message for record in caplog.records)
