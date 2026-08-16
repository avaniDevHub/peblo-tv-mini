"""Storage atomicity — the property the whole publish design rests on."""
from __future__ import annotations

import tempfile

from app.storage.local import LocalStorage


def test_put_atomic_replaces_wholesale():
    d = tempfile.mkdtemp()
    s = LocalStorage(root=d, public_base_url="http://x/media")
    s.put_atomic("catalog/current.json", b'{"v":1}', "application/json")
    assert s.get("catalog/current.json") == b'{"v":1}'
    # Overwrite atomically; reader sees the whole new value, never a mix.
    s.put_atomic("catalog/current.json", b'{"v":2,"more":true}', "application/json")
    assert s.get("catalog/current.json") == b'{"v":2,"more":true}'


def test_put_atomic_leaves_no_temp_files():
    d = tempfile.mkdtemp()
    s = LocalStorage(root=d, public_base_url="http://x/media")
    s.put_atomic("a/b/c.json", b"hello", "application/json")
    import os

    leftovers = [f for _, _, files in os.walk(d) for f in files if f.endswith(".tmp")]
    assert leftovers == []


def test_path_traversal_blocked():
    d = tempfile.mkdtemp()
    s = LocalStorage(root=d, public_base_url="http://x/media")
    try:
        s.put("../../etc/passwd", b"x", "text/plain")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_url_construction():
    d = tempfile.mkdtemp()
    s = LocalStorage(root=d, public_base_url="http://x/media/")
    assert s.url("artwork/1/poster.jpg") == "http://x/media/artwork/1/poster.jpg"
