"""Storage abstraction.

The rest of the app only ever depends on the :class:`Storage` protocol. Swapping
local disk for Cloudflare R2 is a one-line change in the factory below — nothing
in the routers/services changes. See README §"Storage abstraction".
"""
from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .base import Storage
from .local import LocalStorage
from .r2 import R2Storage


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "r2":
        return R2Storage(
            endpoint_url=settings.r2_endpoint_url,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket=settings.r2_bucket,
            public_base_url=settings.r2_public_base_url or settings.media_base_url,
        )
    return LocalStorage(root=settings.storage_local_dir, public_base_url=settings.media_base_url)


__all__ = ["Storage", "LocalStorage", "R2Storage", "get_storage"]
