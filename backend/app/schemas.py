"""Pydantic request/response schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Shows ----------
class ShowCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    section: Optional[str] = None
    synopsis: str = ""
    categories: list[str] = Field(default_factory=list)
    status: str = "draft"


class ShowUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=256)
    section: Optional[str] = None
    synopsis: Optional[str] = None
    categories: Optional[list[str]] = None
    status: Optional[str] = None


class ShowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    title: str
    section: Optional[str]
    synopsis: str
    categories: list[str]
    status: str


# ---------- Seasons ----------
class SeasonCreate(BaseModel):
    season_number: int = Field(ge=0)


class SeasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    show_id: int
    season_number: int
    is_trailer: bool


# ---------- Episodes ----------
class EpisodeCreate(BaseModel):
    season_number: int = Field(ge=0)
    episode_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=256)
    synopsis: str = ""
    duration_seconds: Optional[int] = Field(default=None, ge=1)
    language: str
    content_group: str
    status: str = "draft"
    external_id: Optional[str] = None


class EpisodeUpdate(BaseModel):
    episode_number: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = Field(default=None, max_length=256)
    synopsis: Optional[str] = None
    duration_seconds: Optional[int] = Field(default=None, ge=1)
    language: Optional[str] = None
    content_group: Optional[str] = None
    status: Optional[str] = None


class ArtworkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    width: int
    height: int
    bytes: int
    content_type: str
    url: str = ""


class EpisodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    season_id: int
    external_id: Optional[str]
    episode_number: int
    title: str
    synopsis: str
    duration_seconds: Optional[int]
    language: str
    content_group: str
    status: str
    season_number: int = 0
    artwork: list[ArtworkOut] = Field(default_factory=list)


# ---------- Publish ----------
class PublishRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    started_at: object
    finished_at: Optional[object]
    published_by: str
    outcome: str
    catalog_key: Optional[str]
    show_count: int
    entry_count: int
    detail: dict


class WhoAmIOut(BaseModel):
    username: str
    role: str
