"""Public catalog API — what the *viewer* reads. No auth, read-only.

``GET /catalog`` serves the pre-published file straight from storage (the whole
point of publishing — see README). ``GET /catalog/search`` runs server-side
search over published data. The viewer never touches ``/admin/*``.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..reference import reference
from ..services.search import search_catalog
from ..storage import get_storage

router = APIRouter(tags=["catalog"])
settings = get_settings()


@router.get("/reference")
def get_reference():
    """Public reference data (allowed sections/categories/languages + artwork
    specs). Both UIs read this so allowed values live in exactly one place."""
    return reference()


@router.get("/catalog")
def get_catalog():
    """Serve the published catalogue file verbatim from storage.

    Returns 404 with a clear message if nothing has been published yet, so the
    viewer can show a friendly "coming soon" empty state instead of crashing.
    """
    storage = get_storage()
    if not storage.exists(settings.catalog_current_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No catalogue has been published yet. Ask an admin to publish.",
        )
    body = storage.get(settings.catalog_current_key)
    # Serve raw bytes so we don't re-serialize; add caching headers.
    return Response(
        content=body,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=30"},
    )


@router.get("/catalog/search")
def catalog_search(
    q: str | None = None,
    category: str | None = None,
    language: str | None = None,
    section: str | None = None,
    db: Session = Depends(get_db),
):
    return search_catalog(db, q=q, category=category, language=language, section=section)
