"""
SQLAlchemy engine/session setup.

Reconciled with the repo's existing root-level db.py: both point at the
same shared MySQL (AWS RDS) instance and use the same DB_HOST / DB_PORT /
DB_USER / DB_PASSWORD / DB_NAME env vars. db.py's `connect()` is still the
right choice for raw-SQL scripts (DS1 ingestion, DS2 baseline); this
engine is only for the FastAPI ORM layer added here. They talk to the
same database, not two different ones.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

settings = get_settings()

if settings.database_url.startswith("sqlite"):
    # Used for local/test runs only (e.g. DATABASE_URL=sqlite:///:memory:).
    # A single StaticPool connection keeps the in-memory db alive across
    # requests within a test session. Real runs use the shared MySQL
    # instance built from DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME.
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
