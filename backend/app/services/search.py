"""Catalog search.

Runs *server-side* over the published DB state (not in the browser — see README
§Search on scale). ``q`` matches show title OR episode title OR category;
``category`` / ``language`` / ``section`` filters compose (AND) with each other
and with ``q``. Results are shows (the browsable unit), each annotated with why
it matched, so the viewer can render a normal row of poster cards.
"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..models import STATUS_PUBLISHED, Episode, Season, Show
from ..storage import get_storage


def search_catalog(
    db: Session,
    q: str | None = None,
    category: str | None = None,
    language: str | None = None,
    section: str | None = None,
) -> dict:
    storage = get_storage()

    stmt = (
        select(Show)
        .where(Show.status == STATUS_PUBLISHED)
        .options(selectinload(Show.seasons).selectinload(Season.episodes).selectinload(Episode.artwork))
    )

    # --- section filter (indexed) ---
    if section:
        stmt = stmt.where(Show.section == section)

    # --- language filter: show must have >=1 published episode in that language ---
    if language:
        stmt = stmt.where(
            Show.id.in_(
                select(Season.show_id)
                .join(Episode, Episode.season_id == Season.id)
                .where(Episode.status == STATUS_PUBLISHED, Episode.language == language)
            )
        )

    # --- category filter: JSON array membership.
    # Portable approach: filter in Python after load (catalogs are small; see
    # README). For large catalogs this becomes a jsonb @> query / join table.
    shows = db.execute(stmt.order_by(Show.slug)).scalars().all()

    ql = (q or "").strip().lower()

    def show_matches(show: Show) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if category and category not in (show.categories or []):
            return False, reasons
        if not ql:
            return True, reasons
        if ql in show.title.lower():
            reasons.append("title")
        if any(ql in (c or "").lower() for c in (show.categories or [])):
            reasons.append("category")
        for season in show.seasons:
            for ep in season.episodes:
                if ep.status == STATUS_PUBLISHED and ql in ep.title.lower():
                    reasons.append("episode")
                    break
            if "episode" in reasons:
                break
        return (len(reasons) > 0), reasons

    results = []
    for show in shows:
        ok, reasons = show_matches(show)
        if not ok:
            continue
        # Primary artwork for the poster card.
        poster = banner = None
        primary_eps = [
            ep
            for s in sorted(show.seasons, key=lambda s: s.season_number)
            if not s.is_trailer
            for ep in sorted(s.episodes, key=lambda e: e.episode_number)
            if ep.status == STATUS_PUBLISHED
        ]
        if primary_eps:
            art = {a.kind: storage.url(a.storage_key) for a in primary_eps[0].artwork}
            poster, banner = art.get("poster"), art.get("banner")
        results.append(
            {
                "slug": show.slug,
                "title": show.title,
                "section": show.section,
                "synopsis": show.synopsis,
                "categories": show.categories or [],
                "poster_url": poster,
                "banner_url": banner,
                "matched_on": sorted(set(reasons)) if ql else [],
            }
        )

    return {
        "query": {"q": q, "category": category, "language": language, "section": section},
        "count": len(results),
        "results": results,
    }
