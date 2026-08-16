"""Container bootstrap: seed the DB and (optionally) run a demo publish.

Run by the Docker entrypoint AFTER ``alembic upgrade head``. Fully idempotent —
safe to run on every container start.

Why this exists
---------------
The seed data is deliberately imperfect. In particular ``ep_0036`` is marked
*published* but ships with **no artwork**, which correctly **blocks** a clean
publish. So out of the box ``/catalog`` is empty and the viewer shows its
"nothing published yet" state — which is the honest, correct behaviour.

For a reviewer running ``docker compose up`` we'd rather show a *populated*
viewer without hiding that gate. So this bootstrap:

  1. Seeds ``seed_shows.json`` faithfully (imperfections intact).
  2. Prints the seed report (the surfaced duplicate row, counts).
  3. ALWAYS prints the validation report, so the deliberate block is visible
     in the container logs before anything is fixed.
  4. Only if ``PEBLO_DEMO_PUBLISH=1`` (the compose default): performs the exact
     fix the validation report tells an editor to do — uploads the three sample
     images to ``ep_0036`` through the real ``validate_artwork`` + storage path,
     exactly as the CMS artwork endpoint would — then runs the real publish job.

Set ``PEBLO_DEMO_PUBLISH=0`` to leave the catalogue unpublished and see the
genuine empty-state / validation-gate behaviour instead.
"""
from __future__ import annotations

import json
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Artwork, Episode
from .seed import ASSETS_DIR, SAMPLE_ASSET, seed
from .services.artwork import validate_artwork
from .services.publish import PublishBlocked, run_publish
from .services.validation import validation_report
from .storage import get_storage

# The deliberately-broken row: published, zero artwork -> blocks publish.
DEMO_FIX_EXTERNAL_ID = "ep_0036"


def _print(title: str, obj) -> None:
    print(f"\n=== {title} ===", flush=True)
    print(json.dumps(obj, indent=2, default=str), flush=True)


def _fix_ep_0036(db: Session) -> bool:
    """Upload the 3 sample images to ep_0036 exactly as the CMS endpoint would.

    Returns True if the fix was applied (or already present), False if the row
    isn't there. Uses the real validate+store path — no shortcut that bypasses
    validation — so the demo can't produce artwork the CMS would have rejected.
    """
    ep = db.execute(
        select(Episode).where(Episode.external_id == DEMO_FIX_EXTERNAL_ID)
    ).scalar_one_or_none()
    if ep is None:
        print(f"[bootstrap] {DEMO_FIX_EXTERNAL_ID} not found; nothing to fix.", flush=True)
        return False

    storage = get_storage()
    have = {a.kind for a in ep.artwork}
    for kind, fname in SAMPLE_ASSET.items():
        if kind in have:
            continue
        path = ASSETS_DIR / fname
        if not path.exists():
            print(f"[bootstrap] sample asset missing: {path}", flush=True)
            continue
        data = path.read_bytes()
        # Same validation the editor's upload goes through.
        result = validate_artwork(kind, data, fname)
        if not result.ok:
            print(f"[bootstrap] sample {fname} failed validation: {result.errors}", flush=True)
            continue
        ext = "png" if result.content_type == "image/png" else "jpg"
        key = f"artwork/{ep.id}/{kind}.{ext}"
        storage.put(key, data, result.content_type)
        db.add(
            Artwork(
                episode_id=ep.id,
                kind=kind,
                storage_key=key,
                width=result.width,
                height=result.height,
                bytes=result.bytes,
                content_type=result.content_type,
            )
        )
    db.commit()
    print(f"[bootstrap] {DEMO_FIX_EXTERNAL_ID} artwork ensured (poster/banner/thumbnail).", flush=True)
    return True


def main() -> None:
    demo_publish = os.getenv("PEBLO_DEMO_PUBLISH", "1") == "1"

    db = SessionLocal()
    try:
        # 1) Seed (idempotent). Attaches real sample artwork for the kinds each
        #    row declares available — so ep_0036 genuinely gets none.
        report = seed(db)
        _print("seed report", report)

        # 2) Show the validation gate as-is (the deliberate block is visible).
        _print("validation report (pre-fix)", validation_report(db))

        if not demo_publish:
            print(
                "\n[bootstrap] PEBLO_DEMO_PUBLISH=0 -> leaving catalogue unpublished. "
                "GET /catalog will 404 until an admin fixes the issues and publishes.",
                flush=True,
            )
            return

        # 3) Apply the documented editor fix, then publish for real.
        _fix_ep_0036(db)
        report_after = validation_report(db)
        _print("validation report (post-fix)", report_after)

        try:
            run = run_publish(db, published_by="demo-bootstrap")
            print(
                f"\n[bootstrap] PUBLISHED run #{run.id}: "
                f"{run.show_count} shows, {run.entry_count} entries -> {run.catalog_key}",
                flush=True,
            )
        except PublishBlocked as blocked:
            # If anything still blocks, don't crash the container — the API is
            # still fully usable; the viewer just shows its empty state.
            print(
                f"\n[bootstrap] publish still blocked by {blocked.issue_count} issue(s); "
                "leaving catalogue unpublished. See validation report above.",
                flush=True,
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
