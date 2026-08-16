"""SQLAlchemy ORM models.

Data model shape and why
------------------------
shows (1) ─< seasons (1) ─< episodes (1) ─< artwork
                                       │
                                       └── (content_group, language) unique

* A **show** owns a section, categories, synopsis and status. In the seed data
  every one of those is constant per ``slug``, so they belong on the show, not
  repeated on 18 episode rows.
* A **season** is just (show, season_number). Season 0 is modelled as a normal
  row but flagged ``is_trailer`` so the viewer can special-case it without magic
  numbers leaking into the UI.
* An **episode** carries duration, status and the (content_group, language)
  pair. Artwork lives in its own table because an episode has up to three
  distinct rows (poster/banner/thumbnail), each with its own file + dimensions.

Indexes (justified inline) target the three hot queries: publish (status +
section scans), search (title/category), and catalog reads (by show).
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# Status values shared by shows and episodes.
STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
ARTWORK_KINDS = ("poster", "banner", "thumbnail")


class User(Base):
    """Minimal user table so publish runs can record *who* and roles are real."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # editor | admin
    # Static demo token -> maps request to user. Real system: OIDC subject.
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    __table_args__ = (CheckConstraint("role in ('editor','admin')", name="ck_user_role"),)


class Show(Base):
    __tablename__ = "shows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    # Nullable on purpose: a draft show may not have picked a section yet
    # (the seed's "rhyme-rangers" is exactly this case). Publish requires it.
    section: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    synopsis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    categories: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=STATUS_DRAFT, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    seasons: Mapped[list["Season"]] = relationship(
        back_populates="show", cascade="all, delete-orphan", order_by="Season.season_number"
    )

    __table_args__ = (
        CheckConstraint("status in ('draft','published')", name="ck_show_status"),
        # Publish scans "published shows grouped by section"; search filters by section.
        Index("ix_shows_status_section", "status", "section"),
        # Title search (ILIKE) — see README on scale limits.
        Index("ix_shows_title", "title"),
    )


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("shows.id", ondelete="CASCADE"), nullable=False)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Convention: season 0 == trailers. Denormalised flag so the UI never hard-codes 0.
    is_trailer: Mapped[bool] = mapped_column(default=False, nullable=False)

    show: Mapped["Show"] = relationship(back_populates="seasons")
    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="season", cascade="all, delete-orphan", order_by="Episode.episode_number"
    )

    __table_args__ = (
        UniqueConstraint("show_id", "season_number", name="uq_season_show_number"),
        Index("ix_seasons_show", "show_id"),
    )


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    # external id kept for traceability back to seed / CMS.
    external_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    content_group: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=STATUS_DRAFT, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    season: Mapped["Season"] = relationship(back_populates="episodes")
    artwork: Mapped[list["Artwork"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Core business rule: a content_group has at most one row per language.
        UniqueConstraint("content_group", "language", name="uq_episode_group_language"),
        CheckConstraint("status in ('draft','published')", name="ck_episode_status"),
        CheckConstraint("duration_seconds is null or duration_seconds > 0", name="ck_episode_duration_pos"),
        Index("ix_episodes_season", "season_id"),
        # Publish/validation scan episodes by status.
        Index("ix_episodes_status", "status"),
        # Grouping/collapse step groups by content_group.
        Index("ix_episodes_content_group", "content_group"),
        # Episode-title search.
        Index("ix_episodes_title", "title"),
    )


class Artwork(Base):
    __tablename__ = "artwork"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # poster|banner|thumbnail
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    episode: Mapped["Episode"] = relationship(back_populates="artwork")

    __table_args__ = (
        # One image per (episode, kind); re-upload replaces it.
        UniqueConstraint("episode_id", "kind", name="uq_artwork_episode_kind"),
        CheckConstraint("kind in ('poster','banner','thumbnail')", name="ck_artwork_kind"),
        Index("ix_artwork_episode", "episode_id"),
    )


class PublishRun(Base):
    """One row per publish attempt — the audit trail for the publish job."""

    __tablename__ = "publish_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)  # success | blocked | failed
    # Where the immutable snapshot was written (versioned key).
    catalog_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    show_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # collapsed episode entries
    # Structured detail: blocking issues (if blocked) or a summary (if success).
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("outcome in ('success','blocked','failed')", name="ck_run_outcome"),
        Index("ix_runs_started", "started_at"),
    )
