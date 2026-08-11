"""
ORM models mirroring the REAL shared MySQL schema (confirmed via
`DESCRIBE` against the live `onboarding` database on 2026-08-09 - not
just the ERD deck, which was slightly out of date: no `sensors` /
`sensor_baseline` / `current_readings` tables actually exist. The real
pedestrian-sensing tables are `baseline` and `pedestrian_count_minute`/
`pedestrian_count_hour`, keyed by `location_id` (a `location` row IS the
sensor point when `location_type='sensor'`).

No `users`/`preferences` tables mapped here - per team decision, the
product has no account/login system (privacy concern raised by the
tutor), so nothing is scoped to a signed-in user. The real `route` table
still has a NOT NULL `preference_id` column though - flagged to whoever
owns that table, since nothing here writes to `route` currently so it's
not a blocking conflict yet.

Note: every String column has an explicit length. SQLite/Postgres allow
unbounded VARCHAR, but MySQL (the shared RDS instance) requires a length
on every VARCHAR column or CREATE TABLE fails at startup.
"""

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Location(Base):
    """
    Doubles as both "pedestrian sensor point" (location_type='sensor') and
    "sensory refuge" (location_type='refuge', category one of Park /
    Library / Gallery or museum / Quiet place of worship) - confirmed via
    `SELECT DISTINCT location_type, category FROM location;` against the
    real shared DB (273 rows total).
    """

    __tablename__ = "location"

    location_id: Mapped[int] = mapped_column(primary_key=True)
    location_name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    location_type: Mapped[str | None] = mapped_column(String(50))
    category: Mapped[str | None] = mapped_column(String(100))
    placement: Mapped[str | None] = mapped_column(String(50))


class Baseline(Base):
    """
    Precomputed "typical" pedestrian count for a location at a given
    (day_of_week, hourday) slot - DS2's output. Composite PK, so a
    location has one row per day-of-week/hour-of-day combination.
    """

    __tablename__ = "baseline"

    location_id: Mapped[int] = mapped_column(ForeignKey("location.location_id"), primary_key=True)
    day_of_week: Mapped[int] = mapped_column(Integer, primary_key=True)
    hourday: Mapped[int] = mapped_column(Integer, primary_key=True)
    average_count: Mapped[float] = mapped_column(Float, nullable=False)
    median_count: Mapped[float] = mapped_column(Float, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    recomputed_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)


class PedestrianCountMinute(Base):
    """Near-real-time pedestrian counts, one row per location per minute."""

    __tablename__ = "pedestrian_count_minute"

    location_id: Mapped[int] = mapped_column(ForeignKey("location.location_id"), primary_key=True)
    sensing_datetime: Mapped[DateTime] = mapped_column(DateTime, primary_key=True)
    sensing_date: Mapped[Date] = mapped_column(Date, nullable=False)
    sensing_time: Mapped[Time] = mapped_column(Time, nullable=False)
    direction_1: Mapped[int | None] = mapped_column(Integer)
    direction_2: Mapped[int | None] = mapped_column(Integer)
    total_of_directions: Mapped[int | None] = mapped_column(Integer)


class SensoryReadingRecord(Base):
    """Latest DS1/DS3 integration rows introduced by database PR #14."""

    __tablename__ = "sensory_reading"

    location_id: Mapped[int] = mapped_column(ForeignKey("location.location_id"), primary_key=True)
    window_end: Mapped[DateTime] = mapped_column(DateTime, primary_key=True)
    pedestrian_count: Mapped[int | None] = mapped_column(Integer)
    sensory_status: Mapped[str] = mapped_column(String(20), nullable=False)


class Config(Base):
    """
    Key/value tuning table DS2 writes to (route_buffer_radius_m,
    relative_threshold, absolute_threshold, minimum_observations,
    minimum_route_sensors, live_max_age_minutes - only a subset is
    populated at any given time; missing keys fall back to
    ScoringConfig's own defaults, same as DS3's own load_config()).
    """

    __tablename__ = "config"

    config_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))


class Route(Base):
    __tablename__ = "route"

    route_id: Mapped[int] = mapped_column(primary_key=True)
    start_location_id: Mapped[int] = mapped_column(
        ForeignKey("location.location_id"), nullable=False
    )
    end_location_id: Mapped[int] = mapped_column(ForeignKey("location.location_id"), nullable=False)
    eta: Mapped[int | None] = mapped_column(Integer)
    transportation: Mapped[str | None] = mapped_column(String(50))


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
