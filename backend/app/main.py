"""FastAPI application entrypoint."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .config import get_settings
from .db import engine
from .routers import admin, catalog

settings = get_settings()

app = FastAPI(
    title="Peblo TV Mini API",
    version="1.0.0",
    description="CMS + published catalogue + viewer backend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(catalog.router)

# Serve locally-stored media (artwork) when using the local storage backend.
if settings.storage_backend == "local":
    os.makedirs(settings.storage_local_dir, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.storage_local_dir), name="media")


@app.get("/health", tags=["ops"])
def health():
    """Liveness + readiness in one.

    Checks the DB round-trips. We deliberately DON'T fail health if no catalogue
    is published yet — that's a valid empty state, not an outage. See README
    §Operability for what we alert on and why.
    """
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    status_str = "ok" if db_ok else "degraded"
    return {"status": status_str, "checks": {"database": db_ok}}


@app.get("/", tags=["ops"])
def root():
    return {"service": "peblo-tv-mini", "docs": "/docs", "health": "/health"}
