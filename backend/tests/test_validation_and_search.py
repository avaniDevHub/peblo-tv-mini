"""Validation report grouping + catalog search (composing filters)."""
from __future__ import annotations

from tests.conftest import ADMIN, EDITOR


def test_validation_report_surfaces_seed_defect(client):
    r = client.get("/admin/validation-report", headers=EDITOR)
    assert r.status_code == 200
    report = r.json()
    assert report["blocking"] is True
    codes = {g["code"] for g in report["groups"]}
    # The planted defect: ep_0036 is published without artwork.
    assert "episode_missing_artwork" in codes
    # Each group carries an editor-facing title + fix hint.
    for g in report["groups"]:
        assert g["title"] and g["fix_hint"]


def test_validation_report_requires_auth(client):
    assert client.get("/admin/validation-report").status_code == 401


def _publish(client):
    eps = client.get("/admin/shows/discover-india-with-moti/episodes", headers=ADMIN).json()
    bad = next(e for e in eps if e["external_id"] == "ep_0036")
    client.patch(f"/admin/episodes/{bad['id']}", json={"status": "draft"}, headers=ADMIN)
    client.post("/admin/catalog/publish", headers=ADMIN)


def test_search_matches_show_title(client):
    _publish(client)
    r = client.get("/catalog/search", params={"q": "moti"}).json()
    slugs = {x["slug"] for x in r["results"]}
    assert "motis-many-lives" in slugs


def test_search_matches_category(client):
    _publish(client)
    r = client.get("/catalog/search", params={"category": "maths"}).json()
    assert r["count"] >= 1
    assert all("maths" in x["categories"] for x in r["results"])


def test_search_filters_compose(client):
    _publish(client)
    r = client.get("/catalog/search", params={"section": "songs", "language": "en"}).json()
    assert r["count"] >= 1
    assert all(x["section"] == "songs" for x in r["results"])


def test_search_empty_state(client):
    _publish(client)
    r = client.get("/catalog/search", params={"q": "zzz-no-such-thing"}).json()
    assert r["count"] == 0
    assert r["results"] == []


def test_catalog_404_before_publish(empty_client):
    # Nothing published yet -> friendly 404 for the viewer's empty state.
    assert empty_client.get("/catalog").status_code == 404


def test_viewer_never_needs_admin(client):
    # /catalog and /catalog/search must be reachable with NO auth header.
    _publish(client)
    assert client.get("/catalog").status_code == 200
    assert client.get("/catalog/search").status_code == 200
