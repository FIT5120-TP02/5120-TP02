"""
Central app configuration, loaded from environment variables (.env in dev,
real env vars on the deployment platform - never commit secrets to the repo,
per the Security Plan slide: "Credentials never in the repo").

Database settings deliberately mirror the repo-root db.py env vars
(DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME) so this backend and
DS1's ingestion scripts point at the same shared MySQL (AWS RDS) instance
instead of running two different databases.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Same shared instance db.py defaults to - keep these two files in sync if
# the team ever moves off this RDS instance.
SHARED_DB_HOST = "tp02fit5120.c1qymwwke45u.ap-southeast-2.rds.amazonaws.com"
SHARED_DB_PORT = 3306
SHARED_DB_USER = "admin"
SHARED_DB_NAME = "onboarding"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database - same env var names as db.py, so `export DB_PASSWORD=...`
    # (or the PowerShell/bash snippets in db.py's docstring) work for both.
    db_host: str = SHARED_DB_HOST
    db_port: int = SHARED_DB_PORT
    db_user: str = SHARED_DB_USER
    db_name: str = SHARED_DB_NAME
    db_password: str | None = None

    # Escape hatch for tests / local sqlite runs only: if DATABASE_URL is
    # set directly, it's used as-is and the DB_* fields above are ignored.
    database_url_override: str | None = Field(default=None, validation_alias="DATABASE_URL")

    # No auth/JWT settings - the product has no account/login system
    # (team decision: no user accounts, per tutor's privacy guidance).

    # Routing service integration
    routing_provider: str = "mock"  # "mock" | "osrm" | "graphhopper" | "openrouteservice"
    routing_service_url: str = "http://localhost:5001"
    routing_service_api_key: str = ""

    # Sensory scoring thresholds (DS2/DS3 own the values; these are fallbacks)
    crowd_high_threshold_multiplier: float = 1.5
    min_baseline_observations: int = 5

    # How close a `location` row (location_type='sensor') must be to any
    # point on a candidate route's polyline to count as "on this route".
    # 0.1km = 100m - tight enough that a sensor on a parallel street a
    # block over shouldn't match. Tune once real route density is tested.
    sensor_match_radius_km: float = 0.1

    # `baseline.day_of_week`/`hourday` are matched against the current
    # local time so LOW/HIGH reflects "for a Tuesday 5pm", not "overall".
    # Melbourne CBD - only relevant if this deploys somewhere with a
    # different server timezone (e.g. Render's UTC).
    local_timezone: str = "Australia/Melbourne"

    # CORS
    frontend_origin: str = "http://localhost:5173"

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        if not self.db_password:
            raise RuntimeError(
                "DB_PASSWORD is not set.\n"
                "  PowerShell:  $env:DB_PASSWORD = Read-Host 'Password'\n"
                "  bash:        read -rs DB_PASSWORD && export DB_PASSWORD\n"
                "Ask the team for it - same variable the repo-root db.py uses, "
                "deliberately not in the repository."
            )
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
