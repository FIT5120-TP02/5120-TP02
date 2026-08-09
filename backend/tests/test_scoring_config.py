"""
Tests for app/services/scoring_config.py::load_scoring_config - the
SQLAlchemy equivalent of DS3's sensory_scoring.load_config(), which reads
the shared `config` table via a raw pymysql connection instead.

Review round 4, issue #1: the FastAPI path (app/routers/routes.py) must
actually use DB-configured thresholds, not hardcoded ScoringConfig()
defaults, and a DB override must provably change scoring behaviour.

Every test clears the `config` table first - the test DB (see
tests/conftest.py) is a single in-memory sqlite connection shared across
the whole test session, so a row inserted by one test would otherwise
leak into the next.
"""

from datetime import datetime, timezone

from app.models import Config
from app.services.scoring_config import load_scoring_config
from app.services.sensory_scoring import SensorBaseline, SensorReading, score_route


def _clear_config(db_session):
    db_session.query(Config).delete()
    db_session.commit()


def test_load_scoring_config_reads_populated_keys(db_session):
    _clear_config(db_session)
    # Mirrors the live shared DB's actual config rows as of 2026-08-09 -
    # only these three keys are populated; the rest fall back to defaults.
    db_session.add_all(
        [
            Config(config_key="absolute_threshold", value="500", updated_at=datetime(2026, 8, 7)),
            Config(config_key="minimum_observations", value="10", updated_at=datetime(2026, 8, 7)),
            Config(config_key="relative_threshold", value="1.5", updated_at=datetime(2026, 8, 7)),
        ]
    )
    db_session.commit()

    cfg = load_scoring_config(db_session)

    assert cfg.absolute_threshold == 500
    assert cfg.minimum_observations == 10
    assert cfg.relative_threshold == 1.5
    # Not in the table yet - must fall back to ScoringConfig's own defaults.
    assert cfg.buffer_radius_m == 120.0
    assert cfg.minimum_sensors == 1
    assert cfg.live_max_age_minutes == 30


def test_load_scoring_config_falls_back_to_defaults_when_table_empty(db_session):
    _clear_config(db_session)

    cfg = load_scoring_config(db_session)

    assert cfg.absolute_threshold == 500.0
    assert cfg.relative_threshold == 1.5
    assert cfg.minimum_observations == 10


def test_config_override_changes_scoring_outcome(db_session):
    # Same reading/baseline, two different absolute_threshold overrides -
    # proves the DB value actually reaches score_route(), not just that
    # load_scoring_config() parses it.
    _clear_config(db_session)
    now = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)  # a Monday
    readings = {"1": SensorReading("1", 600, now)}
    baselines = {"1": SensorBaseline("1", 300, 20)}

    db_session.add(
        Config(config_key="absolute_threshold", value="500", updated_at=datetime(2026, 8, 7))
    )
    db_session.commit()
    low_threshold_cfg = load_scoring_config(db_session)
    status_with_low_threshold, _ = score_route(["1"], readings, baselines, low_threshold_cfg, now)
    assert status_with_low_threshold == "HIGH"  # 600 >= 500 and >= 300*1.5

    # Override to a threshold above the current reading - same data, the
    # DB value alone must flip the outcome to LOW.
    row = db_session.query(Config).filter(Config.config_key == "absolute_threshold").one()
    row.value = "1000"
    db_session.commit()
    high_threshold_cfg = load_scoring_config(db_session)
    status_with_high_threshold, _ = score_route(["1"], readings, baselines, high_threshold_cfg, now)
    assert status_with_high_threshold == "LOW"  # 600 < 1000
