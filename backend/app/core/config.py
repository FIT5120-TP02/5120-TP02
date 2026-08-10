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

    # No sensory-scoring threshold settings here - DS3's
    # app/services/sensory_scoring.py::ScoringConfig owns the buffer
    # radius, HIGH thresholds, minimum observations, and staleness window,
    # with its own sensible defaults. It's designed to load overrides from
    # the shared DB's `config` table (see ScoringConfig/load_config) rather
    # than from this app's env vars, so DS2 can tune it without a
    # redeploy.

    # No local-timezone setting here either - DS3's sensory_scoring.py
    # hardcodes Australia/Melbourne for baseline day/hour matching, since
    # that's a property of the data (Melbourne CBD sensors), not something
    # that should vary by deployment.

    # CORS - comma-separated so more than one origin can be allowed at
    # once (e.g. the deployed frontend plus a teammate's local dev
    # server) without needing a separate env var per origin.
    frontend_origin: str = "http://localhost:5173"

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

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
