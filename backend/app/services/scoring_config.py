"""
SQLAlchemy adapter for loading DS3's ScoringConfig from the shared DB's
`config` table.

DS3's own `sensory_scoring.load_config()` does the equivalent thing with
a raw pymysql connection, matching db.py's style - this app's DB session
is a SQLAlchemy Session instead (see app/database.py), so this is a small
port of that same logic rather than a straight call. Same keys, same
fallback defaults, sourced from the same table, confirmed against the
live DB on 2026-08-09: only `absolute_threshold`, `minimum_observations`,
and `relative_threshold` are actually populated right now -
`route_buffer_radius_m`, `minimum_route_sensors`, and
`live_max_age_minutes` fall back to ScoringConfig's own defaults until
DS2 adds rows for them.
"""

from sqlalchemy.orm import Session

from app.models import Config
from app.services.sensory_scoring import ScoringConfig


def load_scoring_config(db: Session) -> ScoringConfig:
    rows = db.query(Config.config_key, Config.value).all()
    values = dict(rows)
    return ScoringConfig(
        buffer_radius_m=float(values.get("route_buffer_radius_m", 120)),
        relative_threshold=float(values.get("relative_threshold", 1.5)),
        absolute_threshold=float(values.get("absolute_threshold", 500)),
        minimum_observations=int(values.get("minimum_observations", 10)),
        minimum_sensors=int(values.get("minimum_route_sensors", 1)),
        live_max_age_minutes=int(values.get("live_max_age_minutes", 30)),
    )
