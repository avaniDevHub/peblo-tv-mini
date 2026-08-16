"""Auth/role enforcement + CRUD business rules."""
from __future__ import annotations

import io

from PIL import Image

from tests.conftest import ADMIN, EDITOR


def _img(w, h):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, "JPEG")
    return buf.getvalue()


# ---------- auth ----------
def test_no_token_is_401(client):
    assert client.get("/admin/shows").status_code == 401


def test_bad_token_is_401(client):
    assert client.get("/admin/shows", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_editor_can_crud_but_not_publish(client):
    assert client.get("/admin/shows", headers=EDITOR).status_code == 200
    r = client.post("/admin/catalog/publish", headers=EDITOR)
    assert r.status_code == 403
    assert "admin" in r.json()["detail"].lower()


def test_admin_can_publish_route(client):
    # (may be 200 or 409 depending on data, but must NOT be 403)
    r = client.post("/admin/catalog/publish", headers=ADMIN)
    assert r.status_code != 403


# ---------- CRUD validation ----------
def test_published_show_requires_section(client):
    r = client.post(
        "/admin/shows",
        json={"slug": "x-show", "title": "X", "status": "published"},  # no section
        headers=EDITOR,
    )
    assert r.status_code == 409
    assert "section" in r.json()["detail"].lower()


def test_duplicate_group_language_rejected(client):
    # Create a show + episode, then a second episode with same (group, lang).
    client.post("/admin/shows", json={"slug": "dup", "title": "Dup", "section": "series"}, headers=EDITOR)
    base = {"season_number": 1, "episode_number": 1, "title": "A", "language": "en", "content_group": "dup-g1"}
    r1 = client.post("/admin/shows/dup/episodes", json=base, headers=EDITOR)
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        "/admin/shows/dup/episodes",
        json={**base, "episode_number": 2, "title": "B"},  # same group+lang
        headers=EDITOR,
    )
    assert r2.status_code == 409
    assert "unique" in r2.json()["detail"].lower() or "already uses" in r2.json()["detail"].lower()


def test_blank_content_group_gets_unique_default_for_each_episode(client):
    client.post("/admin/shows", json={"slug": "multi", "title": "Multi", "section": "series"}, headers=EDITOR)
    base = {"season_number": 1, "episode_number": 1, "title": "A", "language": "en", "content_group": ""}
    r1 = client.post("/admin/shows/multi/episodes", json={**base, "duration_seconds": 100}, headers=EDITOR)
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        "/admin/shows/multi/episodes",
        json={**base, "episode_number": 2, "title": "B", "duration_seconds": 120},
        headers=EDITOR,
    )
    assert r2.status_code == 201, r2.text
    assert r1.json()["content_group"] != r2.json()["content_group"]
    assert r1.json()["content_group"] == "multi-s01e01"
    assert r2.json()["content_group"] == "multi-s01e02"


def test_cannot_publish_episode_without_duration_or_artwork(client):
    client.post("/admin/shows", json={"slug": "np", "title": "NP", "section": "series"}, headers=EDITOR)
    # No duration, no artwork, but status=published -> rejected.
    r = client.post(
        "/admin/shows/np/episodes",
        json={
            "season_number": 1,
            "episode_number": 1,
            "title": "Ep",
            "language": "en",
            "content_group": "np-g1",
            "status": "published",
        },
        headers=EDITOR,
    )
    assert r.status_code == 409
    assert "duration" in r.json()["detail"].lower()


def test_full_episode_lifecycle_with_artwork(client):
    client.post("/admin/shows", json={"slug": "life", "title": "Life", "section": "series"}, headers=EDITOR)
    ep = client.post(
        "/admin/shows/life/episodes",
        json={
            "season_number": 1,
            "episode_number": 1,
            "title": "Pilot",
            "language": "en",
            "content_group": "life-g1",
            "duration_seconds": 300,
            "status": "draft",
        },
        headers=EDITOR,
    ).json()
    eid = ep["id"]

    # Upload the 3 artwork slots.
    for kind, (w, h) in {"poster": (600, 900), "banner": (1280, 720), "thumbnail": (640, 360)}.items():
        r = client.post(
            f"/admin/episodes/{eid}/artwork/{kind}",
            files={"file": (f"{kind}.jpg", _img(w, h), "image/jpeg")},
            headers=EDITOR,
        )
        assert r.status_code == 200, r.text

    # Now publishing the episode should succeed.
    r = client.patch(f"/admin/episodes/{eid}", json={"status": "published"}, headers=EDITOR)
    assert r.status_code == 200, r.text
    assert len(r.json()["artwork"]) == 3


def test_upload_rejects_bad_image_with_editor_errors(client):
    client.post("/admin/shows", json={"slug": "art", "title": "Art", "section": "series"}, headers=EDITOR)
    ep = client.post(
        "/admin/shows/art/episodes",
        json={
            "season_number": 1,
            "episode_number": 1,
            "title": "E",
            "language": "en",
            "content_group": "art-g1",
            "duration_seconds": 100,
        },
        headers=EDITOR,
    ).json()
    # Square image into a poster slot -> 422 with readable errors.
    r = client.post(
        f"/admin/episodes/{ep['id']}/artwork/poster",
        files={"file": ("bad.jpg", _img(900, 900), "image/jpeg")},
        headers=EDITOR,
    )
    assert r.status_code == 422
    assert r.json()["detail"]["errors"]
