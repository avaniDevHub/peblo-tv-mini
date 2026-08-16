"""Admin/CMS API: CRUD, artwork upload, validation report, publish.

Auth: every route requires at least ``editor``. ``publish`` requires ``admin``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import current_user, require_admin, require_editor
from ..db import get_db
from ..models import ARTWORK_KINDS, Artwork, Episode, PublishRun, Season, Show, User
from ..schemas import (
    EpisodeCreate,
    EpisodeOut,
    EpisodeUpdate,
    PublishRunOut,
    ShowCreate,
    ShowOut,
    ShowUpdate,
    WhoAmIOut,
)
from ..services import crud
from ..services.artwork import validate_artwork
from ..services.publish import PublishBlocked, run_publish
from ..services.validation import validation_report
from ..storage import get_storage

router = APIRouter(prefix="/admin", tags=["admin"])


# ---- identity ----
@router.get("/whoami", response_model=WhoAmIOut)
def whoami(user: User = Depends(current_user)):
    return WhoAmIOut(username=user.username, role=user.role)


# ---- shows ----
def _show_out(show: Show) -> ShowOut:
    return ShowOut.model_validate(show)


@router.get("/shows", response_model=list[ShowOut])
def list_shows(
    q: str | None = None,
    section: str | None = None,
    status_: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    stmt = select(Show)
    if section:
        stmt = stmt.where(Show.section == section)
    if status_:
        stmt = stmt.where(Show.status == status_)
    if q:
        stmt = stmt.where(Show.title.ilike(f"%{q}%"))
    shows = db.execute(stmt.order_by(Show.title)).scalars().all()
    return [_show_out(s) for s in shows]


@router.post("/shows", response_model=ShowOut, status_code=status.HTTP_201_CREATED)
def create_show(data: ShowCreate, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    return _show_out(crud.create_show(db, data))


@router.get("/shows/{slug}", response_model=ShowOut)
def get_show(slug: str, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    return _show_out(crud.get_show(db, slug))


@router.patch("/shows/{slug}", response_model=ShowOut)
def update_show(
    slug: str, data: ShowUpdate, db: Session = Depends(get_db), user: User = Depends(require_editor)
):
    return _show_out(crud.update_show(db, slug, data))


@router.delete("/shows/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_show(slug: str, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    crud.delete_show(db, slug)


# ---- episodes ----
def _episode_out(ep: Episode, db: Session) -> EpisodeOut:
    storage = get_storage()
    season = db.get(Season, ep.season_id)
    out = EpisodeOut.model_validate(ep)
    out.season_number = season.season_number if season else 0
    for a in out.artwork:
        # find matching artwork storage_key
        src = next((x for x in ep.artwork if x.id == a.id), None)
        if src:
            a.url = storage.url(src.storage_key)
    return out


@router.get("/shows/{slug}/episodes", response_model=list[EpisodeOut])
def list_episodes(slug: str, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    show = crud.get_show(db, slug)
    seasons = (
        db.execute(
            select(Season)
            .where(Season.show_id == show.id)
            .options(selectinload(Season.episodes).selectinload(Episode.artwork))
            .order_by(Season.season_number)
        )
        .scalars()
        .all()
    )
    out: list[EpisodeOut] = []
    for season in seasons:
        for ep in sorted(season.episodes, key=lambda e: (e.episode_number, e.language)):
            out.append(_episode_out(ep, db))
    return out


@router.post("/shows/{slug}/episodes", response_model=EpisodeOut, status_code=status.HTTP_201_CREATED)
def create_episode(
    slug: str, data: EpisodeCreate, db: Session = Depends(get_db), user: User = Depends(require_editor)
):
    show = crud.get_show(db, slug)
    ep = crud.create_episode(db, show, data)
    return _episode_out(ep, db)


@router.get("/episodes/{episode_id}", response_model=EpisodeOut)
def get_episode(episode_id: int, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    return _episode_out(crud.get_episode(db, episode_id), db)


@router.patch("/episodes/{episode_id}", response_model=EpisodeOut)
def update_episode(
    episode_id: int, data: EpisodeUpdate, db: Session = Depends(get_db), user: User = Depends(require_editor)
):
    return _episode_out(crud.update_episode(db, episode_id, data), db)


@router.delete("/episodes/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_episode(episode_id: int, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    crud.delete_episode(db, episode_id)


# ---- artwork upload ----
@router.post("/episodes/{episode_id}/artwork/{kind}", response_model=EpisodeOut)
async def upload_artwork(
    episode_id: int,
    kind: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    if kind not in ARTWORK_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown artwork slot '{kind}'. Use one of: {', '.join(ARTWORK_KINDS)}.",
        )
    ep = crud.get_episode(db, episode_id)
    data = await file.read()

    result = validate_artwork(kind, data, file.filename)
    if not result.ok:
        # 422 with the list of editor-readable problems.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": result.errors, "slot": kind},
        )

    storage = get_storage()
    ext = "png" if result.content_type == "image/png" else "jpg"
    key = f"artwork/{ep.id}/{kind}.{ext}"
    storage.put(key, data, result.content_type)

    # Upsert the artwork row (one per episode+kind).
    art = next((a for a in ep.artwork if a.kind == kind), None)
    if art is None:
        art = Artwork(episode_id=ep.id, kind=kind)
        db.add(art)
    art.storage_key = key
    art.width = result.width
    art.height = result.height
    art.bytes = result.bytes
    art.content_type = result.content_type
    db.commit()
    db.refresh(ep)
    return _episode_out(ep, db)


# ---- validation report ----
@router.get("/validation-report")
def get_validation_report(db: Session = Depends(get_db), user: User = Depends(require_editor)):
    return validation_report(db)


# ---- publish (ADMIN ONLY) ----
@router.post("/catalog/publish", response_model=PublishRunOut)
def publish(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    try:
        run = run_publish(db, published_by=user.username)
    except PublishBlocked as blocked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Publish blocked: fix the validation issues first.",
                "issue_count": blocked.issue_count,
                "groups": blocked.groups,
            },
        )
    return PublishRunOut.model_validate(run)


@router.get("/publish-runs", response_model=list[PublishRunOut])
def list_runs(limit: int = 20, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    runs = (
        db.execute(select(PublishRun).order_by(PublishRun.started_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [PublishRunOut.model_validate(r) for r in runs]
