"""
Test config: point the app at an in-memory sqlite database instead of the
real MySQL (AWS RDS) database, and use the mock routing provider so tests don't
depend on network access, a live routing service, or filesystem writes.
"""

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ROUTING_PROVIDER"] = "mock"

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    """
    Direct DB access for tests that need to seed rows (e.g. refuges) -
    same in-memory sqlite the app itself uses (see app/database.py: one
    StaticPool connection kept alive for the whole test session).
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
