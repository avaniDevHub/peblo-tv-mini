"""The publish job — build the catalogue and write it to storage atomically.

Design (see README §"Atomic publishing"):

  1. Validate first. If anything blocks, record a ``blocked`` run and DO NOT
     touch the live catalogue.
  2. Build the catalogue as an in-memory dict, deterministically ordered.
  3. Write it to an *immutable, versioned* key  ``catalog/runs/{id}.json``.
  4. Atomically swap the ``current`` pointer key to the new bytes
     (``storage.put_atomic``). A reader hitting ``/catalog`` sees either the
     previous complete file or the new complete file — never a partial one.
  5. Record the run (who/when/counts/outcome).

Idempotency: the ``catalog`` body is a pure function of published DB state and is
byte-stable across runs (deterministic sort, no timestamps inside the body), so
re-publishing unchanged data yields an identical catalogue.

Language grouping: episodes are collapsed by ``content_group`` into a single
entry that lists its available ``languages``.
"""
from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..models import STATUS_PUBLISHED, Episode, PublishRun, Season, Show
from ..reference import sections as ref_sections
from ..storage import get_storage
from .validation import collect_issues, group_issues

settings = get_settings()


class PublishBlocked(Exception):
    """Raised when validation issues prevent publishing."""

    def __init__(self, groups: list[dict], issue_count: int):
        self.groups = groups
        self.issue_count = issue_count
        super().__init__(f"Publish blocked by {issue_count} issue(s).")


def _artwork_by_kind(ep: Episode) -> dict[str, str]:
    storage = get_storage()
    return {a.kind: storage.url(a.storage_key) for a in ep.artwork}


def build_catalog(db: Session) -> dict:
    """Build the catalogue dict from currently-published data. Deterministic."""
    storage = get_storage()

    shows = (
        db.execute(
            select(Show)
            .where(Show.status == STATUS_PUBLISHED)
            .options(
                selectinload(Show.seasons).selectinload(Season.episodes).selectinload(Episode.artwork)
            )
            .order_by(Show.slug)
        )
        .scalars()
        .all()
    )

    section_order = {s: i for i, s in enumerate(ref_sections())}
    sections_map: dict[str, list[dict]] = defaultdict(list)
    show_details: dict[str, dict] = {}
    entry_count = 0

    for show in shows:
        # Skip published shows that can't legally appear (defensive; validation
        # gate already blocks these, but publish must never emit a broken show).
        if not show.section or show.section not in section_order:
            continue

        # Collapse published episodes by content_group.
        # groups: content_group -> {season, epnum, is_trailer, title, synopsis,
        #                            langs: {lang: {duration, thumb}}, artwork}
        groups: dict[str, dict] = {}
        for season in show.seasons:
            for ep in season.episodes:
                if ep.status != STATUS_PUBLISHED:
                    continue
                g = groups.setdefault(
                    ep.content_group,
                    {
                        "content_group": ep.content_group,
                        "season_number": season.season_number,
                        "episode_number": ep.episode_number,
                        "is_trailer": season.is_trailer,
                        "title": ep.title,
                        "synopsis": ep.synopsis,
                        "languages": {},  # lang -> {duration_seconds}
                        "thumbnail": None,
                        "artwork": {},
                    },
                )
                art = _artwork_by_kind(ep)
                # Per-language facts.
                g["languages"][ep.language] = {"duration_seconds": ep.duration_seconds}
                # Representative thumbnail/artwork: prefer 'en', else first seen.
                if g["thumbnail"] is None or ep.language == "en":
                    if art.get("thumbnail"):
                        g["thumbnail"] = art["thumbnail"]
                    # keep richest artwork set for the primary episode
                    if art:
                        g["artwork"] = art

        # Build seasons (normal) and trailers (season 0) separately.
        normal_seasons: dict[int, list[dict]] = defaultdict(list)
        trailers: list[dict] = []
        for g in groups.values():
            langs = sorted(g["languages"].keys())
            entry = {
                "content_group": g["content_group"],
                "title": g["title"],
                "synopsis": g["synopsis"],
                "episode_number": g["episode_number"],
                "languages": langs,
                # per-language duration so the UI can show the right length.
                "duration_seconds": {lang: g["languages"][lang]["duration_seconds"] for lang in langs},
                "thumbnail_url": g["thumbnail"],
            }
            if g["is_trailer"]:
                trailers.append(entry)
            else:
                normal_seasons[g["season_number"]].append(entry)

        # Deterministic ordering everywhere.
        seasons_out = []
        for season_number in sorted(normal_seasons):
            eps = sorted(
                normal_seasons[season_number],
                key=lambda e: (e["episode_number"], e["content_group"]),
            )
            entry_count += len(eps)
            seasons_out.append({"season_number": season_number, "episodes": eps})
        trailers.sort(key=lambda e: (e["episode_number"], e["content_group"]))
        entry_count += len(trailers)

        # Show-level artwork (poster for rows, banner for hero) from the primary
        # episode = lowest normal season, lowest episode number.
        primary_artwork: dict[str, str] = {}
        primary_pool = [g for g in groups.values() if not g["is_trailer"]] or list(groups.values())
        if primary_pool:
            primary = sorted(primary_pool, key=lambda g: (g["season_number"], g["episode_number"]))[0]
            primary_artwork = primary["artwork"]

        # Languages available across the whole show.
        show_langs = sorted({lang for g in groups.values() for lang in g["languages"]})

        card = {
            "slug": show.slug,
            "title": show.title,
            "section": show.section,
            "synopsis": show.synopsis,
            "categories": show.categories or [],
            "languages": show_langs,
            "poster_url": primary_artwork.get("poster"),
            "banner_url": primary_artwork.get("banner"),
        }
        sections_map[show.section].append(card)

        show_details[show.slug] = {
            **card,
            "seasons": seasons_out,
            "trailers": trailers,  # season 0, surfaced separately (not a normal season)
        }

    # Ordered sections following reference.json order; shows sorted by title.
    sections_out = []
    for section in ref_sections():
        cards = sorted(sections_map.get(section, []), key=lambda c: (c["title"], c["slug"]))
        if cards:
            sections_out.append({"key": section, "shows": cards})

    # Featured hero: first show of the "featured" section if present, else first show anywhere.
    hero = None
    featured = next((s for s in sections_out if s["key"] == "featured"), None)
    hero_source = featured["shows"][0] if featured and featured["shows"] else (
        sections_out[0]["shows"][0] if sections_out else None
    )
    if hero_source:
        hero = {
            "slug": hero_source["slug"],
            "title": hero_source["title"],
            "synopsis": hero_source["synopsis"],
            "banner_url": hero_source["banner_url"] or hero_source["poster_url"],
        }

    return {
        "hero": hero,
        "sections": sections_out,
        "shows": show_details,
        "counts": {"shows": len(show_details), "entries": entry_count},
    }


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def run_publish(db: Session, published_by: str) -> PublishRun:
    """Execute a publish. Records a PublishRun row and returns it.

    Raises :class:`PublishBlocked` if validation fails (a ``blocked`` run is
    still recorded so the attempt is auditable).
    """
    storage = get_storage()
    run = PublishRun(published_by=published_by, outcome="failed", started_at=_now())
    db.add(run)
    db.flush()  # get run.id for the versioned key

    try:
        # 1) Gate on validation.
        issues = collect_issues(db)
        if issues:
            groups = [g.__dict__ for g in group_issues(issues)]
            run.outcome = "blocked"
            run.finished_at = _now()
            run.detail = {"issue_count": len(issues), "groups": groups}
            db.commit()
            raise PublishBlocked(groups=groups, issue_count=len(issues))

        # 2) Build catalogue.
        catalog = build_catalog(db)
        versioned_key = f"catalog/runs/{run.id}.json"
        body = {
            "version": run.id,
            "generated_at": run.started_at.isoformat(),
            "catalog": catalog,
        }
        payload = json.dumps(body, ensure_ascii=False, sort_keys=False, indent=2).encode("utf-8")

        # 3) Immutable versioned snapshot first (enables rollback; durable).
        storage.put_atomic(versioned_key, payload, "application/json")
        # 4) Atomic swap of the live pointer. THIS is the moment publish "goes live".
        storage.put_atomic(settings.catalog_current_key, payload, "application/json")

        # 5) Record success.
        run.outcome = "success"
        run.finished_at = _now()
        run.catalog_key = versioned_key
        run.show_count = catalog["counts"]["shows"]
        run.entry_count = catalog["counts"]["entries"]
        run.detail = {"counts": catalog["counts"]}
        db.commit()
        return run

    except PublishBlocked:
        raise
    except Exception as exc:  # noqa: BLE001 - record then re-raise
        db.rollback()
        # Re-fetch/att the run to mark it failed (rollback detached pending state).
        failed = PublishRun(
            published_by=published_by,
            outcome="failed",
            started_at=_now(),
            finished_at=_now(),
            detail={"error": str(exc)},
        )
        db.add(failed)
        db.commit()
        raise
