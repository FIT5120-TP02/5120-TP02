"""
ORM models mirroring the Entity Relation Diagram from the onboarding deck:
users, preferences, route, location, support_location, environment.

DS-owned ingestion/scoring tables (sensors, hourly_counts, sensor_baseline,
current_readings, refuge_locations) live in DS1/DS2/DS3's modules per the
System Architecture slide - they are read here via plain SQL/ORM reflection
in services/sensory_scoring.py rather than redefined, to avoid two teams
owning the same table definition.

Note: every String column has an explicit length. SQLite/Postgres allow
unbounded VARCHAR, but MySQL (the shared RDS instance) requires a length
on every VARCHAR column or CREATE TABLE fails at startup.
"""

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    preferences: Mapped[list["Preference"]] = relationship(back_populates="user")


class Preference(Base):
    __tablename__ = "preferences"

    preference_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    noise_tolerance: Mapped[float | None] = mapped_column(Float)
    light_tolerance: Mapped[float | None] = mapped_column(Float)
    crowd_tolerance: Mapped[float | None] = mapped_column(Float)
    preferred_route_type: Mapped[str | None] = mapped_column(String(50))

    user: Mapped["User"] = relationship(back_populates="preferences")
    routes: Mapped[list["Route"]] = relationship(back_populates="preference")


class Location(Base):
    __tablename__ = "location"

    location_id: Mapped[int] = mapped_column(primary_key=True)
    location_name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    location_type: Mapped[str | None] = mapped_column(String(50))


class Route(Base):
    __tablename__ = "route"

    route_id: Mapped[int] = mapped_column(primary_key=True)
    preference_id: Mapped[int] = mapped_column(
        ForeignKey("preferences.preference_id"), nullable=False
    )
    start_location_id: Mapped[int] = mapped_column(
        ForeignKey("location.location_id"), nullable=False
    )
    end_location_id: Mapped[int] = mapped_column(ForeignKey("location.location_id"), nullable=False)
    eta: Mapped[int | None] = mapped_column(Integer)
    transportation: Mapped[str | None] = mapped_column(String(50))

    preference: Mapped["Preference"] = relationship(back_populates="routes")


class SupportLocation(Base):
    __tablename__ = "support_location"

    support_id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("location.location_id"), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(255))
    support_level: Mapped[float | None] = mapped_column(Float)
    contact: Mapped[str | None] = mapped_column(String(255))
    accessibility: Mapped[str | None] = mapped_column(String(255))


class Environment(Base):
    __tablename__ = "environment"

    data_id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("location.location_id"), nullable=False)
    noise_level: Mapped[float | None] = mapped_column(Float)
    light_level: Mapped[float | None] = mapped_column(Float)
    crowd_level: Mapped[float | None] = mapped_column(Float)
    construction: Mapped[bool | None] = mapped_column(Boolean)
    time: Mapped[str | None] = mapped_column(Time)
    data_source: Mapped[str | None] = mapped_column(String(100))
