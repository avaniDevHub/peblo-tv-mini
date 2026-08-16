"""Seed the database from ``seed_shows.json``.

The seed data is deliberately imperfect. This loader's job is to import it
*faithfully* — NOT to silently clean it — so the validation report can surface
the problems exactly as a real ingest would. Concretely:

  * The duplicate (content_group, language) row (ep_9001 duplicates ep_0004)
    hits the unique constraint. We catch it, skip the row, and record it in the
    seed report so it's visible — mirroring what a real idempotent importer does.
  * Shows with a null section (rhyme-rangers) are imported with section=NULL.
  * Episodes flagged published with no / partial artwork (ep_0036, trailers) are
    imported as-is; the validation report flags them.

Artwork: the seed only lists which *kinds* are "available" (not real files). To
make the viewer show real images we attach placeholder artwork rows built from
the sample assets in ``assets/``, but ONLY for the kinds the seed says exist —
so ep_0036 genuinely has none and trailers genuinely have only a thumbnail.

Idempotent: running twice doesn't duplicate rows (keyed by slug / external_id).
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine
from .models import Artwork, Episode, PublishRun, Season, Show, User
from .services.artwork import validate_artwork

APP_DIR = Path(__file__).parent
SEED_PATH = APP_DIR / "seed_shows.json"
ASSETS_DIR = APP_DIR.parent / "assets"

# Map artwork kind -> a good sample asset we ship, used to synthesize real files.
SAMPLE_ASSET = {
    "poster": "poster_good.jpg",
    "banner": "banner_good.jpg",
    "thumbnail": "thumb_good.jpg",
}


def _ensure_users(db: Session) -> None:
    from .config import get_settings

    settings = get_settings()
    seed_users = [
        ("editor", "editor", settings.editor_token),
        ("admin", "admin", settings.admin_token),
    ]
    for username, role, token in seed_users:
        if not db.execute(select(User).where(User.username == username)).scalar_one_or_none():
            db.add(User(username=username, role=role, token=token))
    db.commit()


def _load_sample_bytes() -> dict[str, tuple[bytes, str]]:
    """Return {kind: (bytes, content_type)} from the shipped good assets."""
    out: dict[str, tuple[bytes, str]] = {}
    for kind, fname in SAMPLE_ASSET.items():
        p = ASSETS_DIR / fname
        if p.exists():
            data = p.read_bytes()
            res = validate_artwork(kind, data, fname)
            out[kind] = (data, res)
    return out


def seed(db: Session, *, attach_artwork: bool = True) -> dict:
    """Import seed_shows.json. Returns a report of what happened."""
    rows = json.loads(SEED_PATH.read_text())
    report = {
        "rows": len(rows),
        "shows_created": 0,
        "episodes_created": 0,
        "artwork_created": 0,
        "skipped_duplicates": [],  # surfaced imperfections
        "notes": [],
    }

    _ensure_users(db)

    samples = _load_sample_bytes() if attach_artwork else {}
    storage = None
    if attach_artwork:
        from .storage import get_storage

        storage = get_storage()

    # Track shows by slug; seed rows repeat show-level fields per episode.
    shows_by_slug: dict[str, Show] = {}
    # Track (content_group, language) we've already inserted to skip dupes.
    seen_group_lang: set[tuple[str, str]] = set()

    for row in rows:
        slug = row["slug"]
        show = shows_by_slug.get(slug)
        if show is None:
            show = db.execute(select(Show).where(Show.slug == slug)).scalar_one_or_none()
        if show is None:
            show = Show(
                slug=slug,
                title=row["show_title"],
                section=row.get("section"),  # may be None (rhyme-rangers) — kept as-is
                synopsis=row.get("synopsis", ""),
                categories=row.get("categories", []),
                # A show is 'published' if any of its rows are published.
                status="draft",
            )
            db.add(show)
            db.flush()
            report["shows_created"] += 1
        shows_by_slug[slug] = show
        # Promote show to published if this row is published.
        if row.get("status") == "published":
            show.status = "published"

        season_number = row["season_number"]
        season = db.execute(
            select(Season).where(Season.show_id == show.id, Season.season_number == season_number)
        ).scalar_one_or_none()
        if season is None:
            season = Season(
                show_id=show.id,
                season_number=season_number,
                is_trailer=(season_number == 0),
            )
            db.add(season)
            db.flush()

        cg, lang = row["content_group"], row["language"]
        # Skip duplicate (content_group, language) — surface it, don't crash.
        if (cg, lang) in seen_group_lang:
            report["skipped_duplicates"].append(
                {
                    "episode_id": row["episode_id"],
                    "content_group": cg,
                    "language": lang,
                    "title": row.get("episode_title"),
                    "reason": "duplicate (content_group, language) — kept the first, skipped this one",
                }
            )
            continue
        # Also skip if already in DB (idempotent re-seed).
        if db.execute(
            select(Episode).where(Episode.content_group == cg, Episode.language == lang)
        ).scalar_one_or_none():
            seen_group_lang.add((cg, lang))
            continue

        ep = Episode(
            season_id=season.id,
            external_id=row["episode_id"],
            episode_number=row["episode_number"],
            title=row["episode_title"],
            synopsis=row.get("synopsis", ""),
            duration_seconds=row.get("duration_seconds"),
            language=lang,
            content_group=cg,
            status=row.get("status", "draft"),
        )
        db.add(ep)
        db.flush()
        seen_group_lang.add((cg, lang))
        report["episodes_created"] += 1

        # Attach real artwork only for the kinds the seed says are available.
        available = row.get("artwork_available") or []
        if attach_artwork:
            for kind in available:
                if kind not in samples:
                    continue
                data, res = samples[kind]
                key = f"artwork/{ep.id}/{kind}.jpg"
                storage.put(key, data, res.content_type)
                db.add(
                    Artwork(
                        episode_id=ep.id,
                        kind=kind,
                        storage_key=key,
                        width=res.width,
                        height=res.height,
                        bytes=res.bytes,
                        content_type=res.content_type,
                    )
                )
                report["artwork_created"] += 1

    db.commit()

    report["notes"].append(
        f"{report['shows_created']} shows, {report['episodes_created']} episodes imported. "
        f"{len(report['skipped_duplicates'])} duplicate row(s) skipped and surfaced."
    )
    return report


def init_and_seed() -> dict:
    """Create tables (for local/sqlite dev; prod uses Alembic) and seed."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        return seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    rep = init_and_seed()
    print(json.dumps(rep, indent=2))
