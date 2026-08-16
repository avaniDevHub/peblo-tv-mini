"""Publish-blocking validation.

Produces the ``/admin/validation-report``: everything currently stopping a clean
publish, grouped by issue type so a content editor can fix each without asking an
engineer. The same function is the gate the publish job runs first.

Rules enforced (from the challenge spec + reference.json conventions):
  * A published show must have a section.
  * A published episode must have a duration and all required artwork.
      - Season 0 (trailers) is exempt from the *poster/banner* requirement; a
        trailer only needs a thumbnail (matches the seed's trailer rows).
  * (content_group, language) must be unique — duplicates are a hard block.
  * A published show should have at least one publishable episode.
  * section / category / language values must be in the allowed reference lists.

Each issue carries the ids and a human message. Issues are grouped by ``code``.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import STATUS_PUBLISHED, Artwork, Episode, Season, Show
from ..reference import categories as ref_categories
from ..reference import languages as ref_languages
from ..reference import sections as ref_sections

# Artwork a normal published episode must have.
REQUIRED_ARTWORK = {"poster", "banner", "thumbnail"}
# Trailers (season 0) only need a thumbnail to appear.
REQUIRED_ARTWORK_TRAILER = {"thumbnail"}


@dataclass
class Issue:
    code: str  # machine code, used to group
    message: str  # editor-readable
    show_slug: str | None = None
    show_title: str | None = None
    episode_external_id: str | None = None
    episode_title: str | None = None


@dataclass
class ValidationGroup:
    code: str
    title: str
    fix_hint: str
    issues: list[dict] = field(default_factory=list)


# Friendly titles + fix hints per code, shown at the top of each group in the CMS.
GROUP_META = {
    "show_missing_section": (
        "Published shows without a section",
        "Open the show and choose a section (featured, series, minisodes or songs).",
    ),
    "show_invalid_section": (
        "Shows with an unknown section",
        "Pick one of the allowed sections from the dropdown.",
    ),
    "show_no_publishable_episodes": (
        "Published shows with nothing to show",
        "Publish at least one complete episode, or set the show back to draft.",
    ),
    "episode_missing_duration": (
        "Published episodes missing a duration",
        "Enter the episode length (in seconds) on the episode form.",
    ),
    "episode_missing_artwork": (
        "Published episodes missing artwork",
        "Upload the missing image(s) in the artwork slots on the episode form.",
    ),
    "duplicate_group_language": (
        "Duplicate language variants",
        "Two episodes claim the same content group + language. Delete or re-tag one of them.",
    ),
    "invalid_language": (
        "Episodes with an unknown language",
        "Set the language to one of the allowed codes (en, hi).",
    ),
    "invalid_category": (
        "Shows with an unknown category",
        "Remove or correct categories not in the allowed list.",
    ),
}


def _episode_artwork_kinds(ep: Episode) -> set[str]:
    return {a.kind for a in ep.artwork}


def collect_issues(db: Session) -> list[Issue]:
    """Return every publish-blocking (or publish-relevant) issue in the DB."""
    issues: list[Issue] = []

    allowed_sections = set(ref_sections())
    allowed_categories = set(ref_categories())
    allowed_languages = set(ref_languages())

    shows = (
        db.execute(
            select(Show).options(
                selectinload(Show.seasons).selectinload(Season.episodes).selectinload(Episode.artwork)
            )
        )
        .scalars()
        .all()
    )

    for show in shows:
        published_show = show.status == STATUS_PUBLISHED

        # --- show-level ---
        if published_show and not show.section:
            issues.append(
                Issue(
                    "show_missing_section",
                    f"“{show.title}” is set to Published but has no section.",
                    show.slug,
                    show.title,
                )
            )
        elif show.section and show.section not in allowed_sections:
            issues.append(
                Issue(
                    "show_invalid_section",
                    f"“{show.title}” has section '{show.section}', which isn’t an allowed section.",
                    show.slug,
                    show.title,
                )
            )

        for cat in show.categories or []:
            if cat not in allowed_categories:
                issues.append(
                    Issue(
                        "invalid_category",
                        f"“{show.title}” lists category '{cat}', which isn’t in the allowed list.",
                        show.slug,
                        show.title,
                    )
                )

        # --- episode-level ---
        publishable_count = 0
        for season in show.seasons:
            required = REQUIRED_ARTWORK_TRAILER if season.is_trailer else REQUIRED_ARTWORK
            for ep in season.episodes:
                if ep.status != STATUS_PUBLISHED:
                    continue

                ep_ok = True

                if ep.language not in allowed_languages:
                    issues.append(
                        Issue(
                            "invalid_language",
                            f"Episode “{ep.title}” ({show.title}) has language "
                            f"'{ep.language}', which isn’t allowed.",
                            show.slug,
                            show.title,
                            ep.external_id,
                            ep.title,
                        )
                    )
                    ep_ok = False

                if not ep.duration_seconds or ep.duration_seconds <= 0:
                    issues.append(
                        Issue(
                            "episode_missing_duration",
                            f"Episode “{ep.title}” ({show.title}) is Published but has no duration.",
                            show.slug,
                            show.title,
                            ep.external_id,
                            ep.title,
                        )
                    )
                    ep_ok = False

                have = _episode_artwork_kinds(ep)
                missing = required - have
                if missing:
                    pretty = ", ".join(sorted(missing))
                    issues.append(
                        Issue(
                            "episode_missing_artwork",
                            f"Episode “{ep.title}” ({show.title}) is Published but is "
                            f"missing artwork: {pretty}.",
                            show.slug,
                            show.title,
                            ep.external_id,
                            ep.title,
                        )
                    )
                    ep_ok = False

                if ep_ok and not season.is_trailer:
                    publishable_count += 1

        if published_show and publishable_count == 0:
            issues.append(
                Issue(
                    "show_no_publishable_episodes",
                    f"“{show.title}” is Published but has no complete, publishable episodes.",
                    show.slug,
                    show.title,
                )
            )

    # --- global uniqueness: (content_group, language) ---
    dupes = (
        db.execute(
            select(Episode.content_group, Episode.language, func.count(Episode.id))
            .group_by(Episode.content_group, Episode.language)
            .having(func.count(Episode.id) > 1)
        )
    ).all()
    for content_group, language, count in dupes:
        issues.append(
            Issue(
                "duplicate_group_language",
                f"{count} episodes share content group '{content_group}' + language "
                f"'{language}'. Only one is allowed.",
            )
        )

    return issues


def group_issues(issues: list[Issue]) -> list[ValidationGroup]:
    """Group flat issues by code for the report/UI."""
    by_code: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        by_code[issue.code].append(issue)

    groups: list[ValidationGroup] = []
    for code, items in by_code.items():
        title, hint = GROUP_META.get(code, (code, ""))
        groups.append(
            ValidationGroup(
                code=code,
                title=title,
                fix_hint=hint,
                issues=[
                    {k: v for k, v in asdict(i).items() if k != "code"} for i in items
                ],
            )
        )
    # Deterministic ordering by code so the report is stable.
    groups.sort(key=lambda g: g.code)
    return groups


def validation_report(db: Session) -> dict:
    issues = collect_issues(db)
    groups = group_issues(issues)
    return {
        "blocking": len(issues) > 0,
        "issue_count": len(issues),
        "groups": [asdict(g) for g in groups],
    }
