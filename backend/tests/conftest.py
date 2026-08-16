"""Test fixtures: isolated SQLite DB + temp storage per test module."""
from __future__ import annotations

import os
import tempfile

import pytest

# Configure env BEFORE importing app modules (settings are cached).
_TMP = tempfile.mkdtemp(prefix="peblo-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["STORAGE_LOCAL_DIR"] = f"{_TMP}/storage"
os.environ["MEDIA_BASE_URL"] = "http://testserver/media"
os.environ["EDITOR_TOKEN"] = "editor-token"
os.environ["ADMIN_TOKEN"] = "admin-token"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402
from app.db import SessionLocal  # noqa: E402

ADMIN = {"Authorization": "Bearer admin-token"}
EDITOR = {"Authorization": "Bearer editor-token"}


def _reset_storage():
    """Wipe the local storage dir so catalogue/artwork don't leak across tests.

    Note: get_settings()/get_storage() are lru_cached, so the live storage
    instance's root is the source of truth (not necessarily the env var, which
    other test modules may have set at import time). Wipe *its* root.
    """
    import shutil

    from app.storage import get_storage

    storage_dir = str(get_storage().root)
    shutil.rmtree(storage_dir, ignore_errors=True)
    os.makedirs(storage_dir, exist_ok=True)


@pytest.fixture()
def db():
    # Fresh schema AND fresh storage per test for full isolation.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _reset_storage()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded_db(db):
    seed(db)
    return db


@pytest.fixture()
def client(seeded_db):
    return TestClient(app)


@pytest.fixture()
def empty_client(db):
    return TestClient(app)
