"""Application configuration.

Everything is driven by environment variables so the same image runs in dev,
CI and prod. See ``.env.example`` at the repo root for the full list.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database ---
    # Postgres in docker-compose; sqlite is used by the test-suite.
    database_url: str = "postgresql+psycopg2://peblo:peblo@localhost:5432/peblo"

    # --- Storage ---
    # "local" writes to disk; "r2" talks to Cloudflare R2 / any S3-compatible store.
    storage_backend: str = "local"
    storage_local_dir: str = "./storage"  # instead of "/data/storage"
    # Base URL the browser uses to fetch media. For local storage the API serves
    # /media/*; for R2 this becomes the public bucket / CDN URL.
    media_base_url: str = "http://localhost:8000/media"

    # S3/R2 settings (only used when storage_backend == "r2")
    r2_endpoint_url: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str | None = None
    r2_public_base_url: str | None = None

    # --- Auth ---
    # Static bearer tokens for the demo. In prod these become OIDC/JWT (see README).
    editor_token: str = "editor-token"
    admin_token: str = "admin-token"

    # --- Catalog ---
    catalog_current_key: str = "catalog/current.json"

    # --- App ---
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
