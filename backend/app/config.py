"""Environment-driven configuration. Single source of truth for settings.

Phase 0 only reads DATABASE_URL and CORS_ORIGINS. Every later-phase field is
declared here now with a safe default so later phases add behavior, not new
plumbing — see ARCHITECTURE.md and BUILDPHASES.md Phase 0 §2.
"""
from datetime import datetime
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DOT"
    app_version: str = "0.1.0"
    environment: str = "development"

    # --- Phase 0: required ---
    database_url: str

    # CORS_ORIGINS arrives as a plain comma-separated string
    # ("http://a,http://b"), not JSON — kept as a raw string field so
    # pydantic-settings never tries to JSON-decode it, and exposed as a
    # list through the `cors_origins` property below. Never defaults to a
    # wildcard: an empty/missing CORS_ORIGINS yields an empty allowlist
    # (reject everything), not permissive access.
    cors_origins_raw: str = Field(default="", validation_alias="CORS_ORIGINS")

    # --- Phase 1+: auth ---
    jwt_secret: str | None = None
    jwt_access_ttl_min: int = 30
    jwt_refresh_ttl_days: int = 7
    enable_demo_login: bool = False
    demo_password: str | None = None
    enable_demo_reset: bool = False

    # --- Phase 2+: hash chain signing ---
    signing_master_key: str | None = None

    # --- Demo time base (see ARCHITECTURE.md §4.10) ---
    demo_now: str | None = None

    # --- Phase 7: real-time ---
    redis_url: str | None = None

    # --- Phase 3: public endpoint rate limits ---
    public_verify_rate_limit: str = "30/minute"
    public_report_rate_limit: str = "5/minute"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def demo_now_dt(self) -> datetime:
        """The fixed demo "now" every seeded date and status derivation is
        computed against — ARCHITECTURE.md §4.10. Deliberately not real
        wall-clock time: the frontend's own day-math is pinned to this same
        constant, so drifting here would desync "days to expiry" displays."""
        if not self.demo_now:
            raise RuntimeError("DEMO_NOW is not configured")
        return datetime.fromisoformat(self.demo_now)


@lru_cache
def get_settings() -> Settings:
    return Settings()
