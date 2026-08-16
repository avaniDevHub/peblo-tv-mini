"""Authentication & role enforcement.

Demo auth is a static bearer token per user (seeded in the DB). The dependency
resolves the token to a ``User`` row and the role helpers enforce access. This is
*actually enforced* at the endpoint layer — see ``require_admin`` on the publish
route. In production the bearer token becomes a verified OIDC/JWT (README §Auth).
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import User


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Use 'Authorization: Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization.split(" ", 1)[1].strip()


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_token(authorization)
    user = db.execute(select(User).where(User.token == token)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_editor(user: User = Depends(current_user)) -> User:
    """Editors and admins can both do CRUD."""
    if user.role not in ("editor", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor or admin role required.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    """Only admins may publish."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to publish. Your role is 'editor'.",
        )
    return user
