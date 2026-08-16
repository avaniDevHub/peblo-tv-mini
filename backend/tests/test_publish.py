"""Publish job — the highest-value logic: atomic, recorded, idempotent, grouped.

Runs over the seeded (deliberately imperfect) dataset via the HTTP API.
"""
from __future__ import annotations

import json

from tests.conftest import ADMIN, EDITOR


def _make_publishable(client):
    """The seed has one blocker: ep_0036 published w/o artwork. Draft it."""
    eps = client.get("/admin/shows/discover-india-with-moti/episodes", headers=ADMIN).json()
    bad = next(e for e in eps if e["external_id"] == "ep_0036")
    r = client.patch(f"/admin/episodes/{bad['id']}", json={"status": "draft"}, headers=ADMIN)
    assert r.status_code == 200, r.text


def test_seed_blocks_publish_until_fixed(client):
    # Out of the box, the seed data blocks publish (ep_0036 missing artwork).
    r = client.post("/admin/catalog/publish", headers=ADMIN)
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["issue_count"] >= 1
    codes = {g["code"] for g in detail["groups"]}
    assert "episode_missing_artwork" in codes


def test_publish_success_records_run(client):
    _make_publishable(client)
    r = client.post("/admin/catalog/publish", headers=ADMIN)
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["outcome"] == "success"
    assert run["show_count"] == 7  # rhyme-rangers (draft/no section) excluded
    assert run["entry_count"] > 0
    assert run["published_by"] == "admin"
    assert run["catalog_key"].startswith("catalog/runs/")

    # Recorded in run history.
    runs = client.get("/admin/publish-runs", headers=EDITOR).json()
    assert any(x["outcome"] == "success" for x in runs)


def test_publish_is_idempotent(client):
    _make_publishable(client)
    client.post("/admin/catalog/publish", headers=ADMIN)
    body1 = client.get("/catalog").json()["catalog"]
    client.post("/admin/catalog/publish", headers=ADMIN)
    body2 = client.get("/catalog").json()["catalog"]
    # Catalogue body is a pure function of published state -> identical.
    assert body1 == body2


def test_language_grouping_collapses_variants(client):
    _make_publishable(client)
    client.post("/admin/catalog/publish", headers=ADMIN)
    cat = client.get("/catalog").json()["catalog"]
    moti = cat["shows"]["motis-many-lives"]

    # Show advertises both languages.
    assert set(moti["languages"]) == {"en", "hi"}

    # S1E1 is ONE entry listing both languages, with per-language durations.
    s1 = next(s for s in moti["seasons"] if s["season_number"] == 1)
    e1 = next(e for e in s1["episodes"] if e["episode_number"] == 1)
    assert set(e1["languages"]) == {"en", "hi"}
    assert e1["duration_seconds"]["en"] == 510
    assert e1["duration_seconds"]["hi"] == 480
    # en + hi collapsed => 10 entries, not 20.
    assert len(s1["episodes"]) == 10


def test_season_zero_is_not_a_normal_season(client):
    _make_publishable(client)
    client.post("/admin/catalog/publish", headers=ADMIN)
    cat = client.get("/catalog").json()["catalog"]
    moti = cat["shows"]["motis-many-lives"]
    # Season 0 never appears among normal seasons...
    assert 0 not in [s["season_number"] for s in moti["seasons"]]
    # ...but the trailer is available separately.
    assert len(moti["trailers"]) == 1
    assert moti["trailers"][0]["title"] == "Trailer"


def test_catalog_ordering_is_deterministic(client):
    _make_publishable(client)
    client.post("/admin/catalog/publish", headers=ADMIN)
    cat = client.get("/catalog").json()["catalog"]
    # Sections follow reference.json order.
    keys = [s["key"] for s in cat["sections"]]
    assert keys == [k for k in ["featured", "series", "minisodes", "songs"] if k in keys]
    # Shows within a section sorted by title.
    for section in cat["sections"]:
        titles = [c["title"] for c in section["shows"]]
        assert titles == sorted(titles)


def test_only_published_shows_appear(client):
    _make_publishable(client)
    client.post("/admin/catalog/publish", headers=ADMIN)
    cat = client.get("/catalog").json()["catalog"]
    # rhyme-rangers is all-draft with no section -> must not appear.
    assert "rhyme-rangers" not in cat["shows"]


def test_atomic_current_pointer_after_second_publish(client):
    """A reader must always see a complete catalogue, and the pointer must move
    forward to the newest run's snapshot."""
    _make_publishable(client)
    r1 = client.post("/admin/catalog/publish", headers=ADMIN).json()
    r2 = client.post("/admin/catalog/publish", headers=ADMIN).json()
    assert r2["id"] > r1["id"]
    # current.json == the newest versioned snapshot (valid, complete JSON).
    current = client.get("/catalog").json()
    assert current["version"] == r2["id"]
