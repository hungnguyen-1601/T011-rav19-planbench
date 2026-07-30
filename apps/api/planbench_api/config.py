"""Application settings from environment variables (PLANBENCH_*)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLANBENCH_", env_file=".env", extra="ignore")

    app_name: str = "PlanBench API"
    version: str = "0.1.0"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]
    # Upper bound for WebSocket playback pacing (messages per second).
    ws_max_rate_hz: float = 60.0

    # Auth. An empty secret means "generate a random one per process":
    # fine for development, and no secret ever lives in the repository.
    # Production must set PLANBENCH_JWT_SECRET (see docs/DEPLOYMENT.md).
    jwt_secret: str = ""
    jwt_ttl_minutes: int = 60
    # "name:role:password" entries, comma separated. Empty -> generated
    # development users with random passwords logged at startup.
    seed_users: str = ""

    # Artifact storage root for trajectories and reports.
    artifact_dir: str = "artifacts"

    # Background worker: hard cap on concurrent benchmark jobs so a few
    # large runs cannot starve the API process.
    worker_concurrency: int = 2

    # Experiment tracking. Empty URI -> tracking disabled (null tracker).
    mlflow_tracking_uri: str = ""
    mlflow_experiment: str = "planbench"


@lru_cache
def get_settings() -> Settings:
    return Settings()
