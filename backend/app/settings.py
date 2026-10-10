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
    public_url: str = "http://localhost:3000"            # link put in alert messages
    # WhatsApp alerts: provider "none" (log only), "meta" (WhatsApp Cloud API) or "twilio"
    whatsapp_provider: str = "none"
    meta_wa_token: str = ""
    meta_wa_phone_id: str = ""
    meta_wa_template: str = ""                         # approved template name; empty = free-form text (24 h window)
    meta_wa_template_lang: str = "en"
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"  # Twilio sandbox number by default
    twilio_content_sid: str = ""                       # HX... Content Template with two variables; used when Twilio refuses free text
    monitor_minutes: int = 30                          # how often signed-in plants with WhatsApp on are checked
    monitor_enabled: bool = True
    max_whatsapp_per_day: int = 10
    monitor_token: str = ""                            # secret for POST /internal/monitor (external cron); empty = endpoint off

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
