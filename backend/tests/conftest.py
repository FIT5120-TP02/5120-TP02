"""
Test config: point the app at an in-memory sqlite database instead of the
real MySQL (AWS RDS) database, and use the mock routing provider so tests don't
depend on network access, a live routing service, or filesystem writes.
"""

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["ROUTING_PROVIDER"] = "mock"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
