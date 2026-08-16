"""CRUD helpers with the challenge's business-rule validation baked in.

Validation raised here becomes HTTP 409/422 in the routers with an
editor-readable ``detail``. The rules that must hold *at write time*:

  * An episode can't be set to ``published`` without artwork AND a duration.
      - Season 0 trailers only need a thumbnail.
  * (content_group, language) must be unique  (DB constraint + friendly check).
  * A show can't be set to ``published`` without a section.

Structural issues that depend on *other* rows (e.g. a published show with zero
complete episodes) live in the validation report, not here.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    STATUS_PUBLISHED,
    Artwork,
    Episode,
    Season,
    Show,
)
from ..reference import categories as ref_categories
from ..reference import languages as ref_languages
from ..reference import sections as ref_sections
from ..services.validation import REQUIRED_ARTWORK, REQUIRED_ARTWORK_TRAILER


def _conflict(detail: str):
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _bad_request(detail: str):
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _not_found(detail: str):
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


# ---------------- Shows ----------------
def get_show(db: Session, slug: str) -> Show:
    show = db.execute(select(Show).where(Show.slug == slug)).scalar_one_or_none()
    if not show:
        raise _not_found(f"No show with slug '{slug}'.")
    return show


def validate_show_publishable(show: Show) -> None:
    if show.status == STATUS_PUBLISHED and not show.section:
        raise _conflict("A published show must have a section. Choose one before publishing this show.")
    if show.section and show.section not in ref_sections():
        raise _bad_request(
            f"'{show.section}' isn't an allowed section. Allowed: {', '.join(ref_sections())}."
        )
    for c in show.categories or []:
        if c not in ref_categories():
            raise _bad_request(f"'{c}' isn't an allowed category.")


def create_show(db: Session, data) -> Show:
    if db.execute(select(Show).where(Show.slug == data.slug)).scalar_one_or_none():
        raise _conflict(f"A show with slug '{data.slug}' already exists.")
    show = Show(
        slug=data.slug,
        title=data.title,
        section=data.section,
        synopsis=data.synopsis,
        categories=data.categories,
        status=data.status,
    )
    validate_show_publishable(show)
    db.add(show)
    db.commit()
    db.refresh(show)
    return show


def update_show(db: Session, slug: str, data) -> Show:
    show = get_show(db, slug)
    for field_ in ("title", "section", "synopsis", "categories", "status"):
        val = getattr(data, field_)
        if val is not None:
            setattr(show, field_, val)
    validate_show_publishable(show)
    db.commit()
    db.refresh(show)
    return show


def delete_show(db: Session, slug: str) -> None:
    show = get_show(db, slug)
    db.delete(show)
    db.commit()


# ---------------- Seasons ----------------
def get_or_create_season(db: Session, show: Show, season_number: int) -> Season:
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
    return season


# ---------------- Episodes ----------------
def _default_content_group(show: Show, season: Season, episode_number: int) -> str:
    slug = (show.slug or "show").strip().lower().replace(" ", "-")
    return f"{slug}-s{season.season_number:02d}e{episode_number:02d}"


def _normalise_content_group(show: Show, season: Season, episode_number: int, raw_group: str | None) -> str:
    value = (raw_group or "").strip()
    return value if value else _default_content_group(show, season, episode_number)


def _check_group_language_unique(db: Session, content_group: str, language: str, exclude_id: int | None):
    stmt = select(Episode).where(
        Episode.content_group == content_group, Episode.language == language
    )
    existing = db.execute(stmt).scalars().all()
    for e in existing:
        if e.id != exclude_id:
            raise _conflict(
                f"Another episode already uses content group '{content_group}' in "
                f"language '{language}'. Each language variant must be unique."
            )


def validate_episode_publishable(db: Session, ep: Episode, season: Season) -> None:
    if ep.language not in ref_languages():
        raise _bad_request(
            f"'{ep.language}' isn't an allowed language. Allowed: {', '.join(ref_languages())}."
        )
    if ep.status != STATUS_PUBLISHED:
        return
    if not ep.duration_seconds or ep.duration_seconds <= 0:
        raise _conflict("An episode can't be published without a duration. Add the length first.")
    required = REQUIRED_ARTWORK_TRAILER if season.is_trailer else REQUIRED_ARTWORK
    have = {a.kind for a in ep.artwork}
    missing = required - have
    if missing:
        raise _conflict(
            f"An episode can't be published without artwork. Missing: {', '.join(sorted(missing))}."
        )


def create_episode(db: Session, show: Show, data) -> Episode:
    season = get_or_create_season(db, show, data.season_number)
    content_group = _normalise_content_group(show, season, data.episode_number, data.content_group)
    _check_group_language_unique(db, content_group, data.language, None)
    ep = Episode(
        season_id=season.id,
        external_id=data.external_id,
        episode_number=data.episode_number,
        title=data.title,
        synopsis=data.synopsis,
        duration_seconds=data.duration_seconds,
        language=data.language,
        content_group=content_group,
        status=data.status,
    )
    # Attach so validation can see (empty) artwork list.
    ep.artwork = []
    validate_episode_publishable(db, ep, season)
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def get_episode(db: Session, episode_id: int) -> Episode:
    ep = db.execute(
        select(Episode).where(Episode.id == episode_id).options(selectinload(Episode.artwork))
    ).scalar_one_or_none()
    if not ep:
        raise _not_found(f"No episode with id {episode_id}.")
    return ep


def update_episode(db: Session, episode_id: int, data) -> Episode:
    ep = get_episode(db, episode_id)
    season = db.get(Season, ep.season_id)
    if season is None:
        raise _not_found(f"No season for episode id {episode_id}.")

    new_group = data.content_group if data.content_group is not None else ep.content_group
    if new_group is not None and not str(new_group).strip():
        new_group = _default_content_group(
            db.get(Show, season.show_id) or Show(slug="show", title="Show", status="draft"),
            season,
            data.episode_number if data.episode_number is not None else ep.episode_number,
        )
    else:
        new_group = str(new_group or ep.content_group).strip() or ep.content_group
    new_lang = data.language if data.language is not None else ep.language
    if (new_group, new_lang) != (ep.content_group, ep.language):
        _check_group_language_unique(db, new_group, new_lang, ep.id)

    for field_ in ("episode_number", "title", "synopsis", "duration_seconds", "language", "content_group", "status"):
        val = getattr(data, field_)
        if val is not None:
            if field_ == "content_group":
                val = str(val).strip() or _default_content_group(
                    db.get(Show, season.show_id) or Show(slug="show", title="Show", status="draft"),
                    season,
                    ep.episode_number,
                )
            setattr(ep, field_, val)

    validate_episode_publishable(db, ep, season)
    db.commit()
    db.refresh(ep)
    return ep


def delete_episode(db: Session, episode_id: int) -> None:
    ep = get_episode(db, episode_id)
    db.delete(ep)
    db.commit()
