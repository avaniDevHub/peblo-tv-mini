"""Storage protocol — the single seam between the app and any object store."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Storage(Protocol):
    """A minimal object-store interface.

    Implementations must make :meth:`put_atomic` durable and all-or-nothing:
    a concurrent reader must never observe a partially written object.
    """

    def put(self, key: str, data: bytes, content_type: str) -> str:
        """Store ``data`` at ``key`` (overwrite ok). Returns the key."""
        ...

    def put_atomic(self, key: str, data: bytes, content_type: str) -> str:
        """Store ``data`` at ``key`` atomically. Readers see old-or-new, never partial."""
        ...

    def get(self, key: str) -> bytes:
        """Fetch bytes. Raises FileNotFoundError / KeyError if missing."""
        ...

    def exists(self, key: str) -> bool:
        ...

    def delete(self, key: str) -> None:
        ...

    def url(self, key: str) -> str:
        """Public URL a browser can use to fetch this object."""
        ...
