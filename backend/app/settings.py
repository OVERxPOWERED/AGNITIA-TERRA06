"""Backend settings from environment variables prefixed TERRA_ (see backend/.env.example)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TERRA_", env_file=".env", extra="ignore")

    mode: Literal["live", "replay"] = "replay"
    replay_start: str = "2026-04-10T00:00"
    replay_step_hours: int = 6
    schedule_minutes: int = 60
    scheduler_enabled: bool = True
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    db_url: str = "sqlite:///./terra.db"
    version: str = "0.1.0"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
