"""Local-disk storage. Default for dev / docker-compose.

Atomic writes use the classic write-tmp-then-``os.replace`` trick: ``os.replace``
is atomic on POSIX within a filesystem, so a reader opening the target path sees
either the previous file or the new one — never a half-written buffer.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


class LocalStorage:
    def __init__(self, root: str, public_base_url: str):
        self.root = Path(root)
        self.public_base_url = public_base_url.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Prevent path traversal; keys are app-generated but be defensive.
        safe = key.lstrip("/")
        p = (self.root / safe).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError(f"unsafe storage key: {key!r}")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def put_atomic(self, key: str, data: bytes, content_type: str) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Same directory => same filesystem => os.replace is atomic.
        fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())  # durability: survive a crash after replace
            os.replace(tmp, p)  # atomic swap
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def url(self, key: str) -> str:
        return f"{self.public_base_url}/{key.lstrip('/')}"
