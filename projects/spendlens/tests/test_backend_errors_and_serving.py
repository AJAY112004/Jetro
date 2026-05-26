from __future__ import annotations

from app import app as flask_app


def test_api_404_returns_json():
    client = flask_app.test_client()
    resp = client.get("/api/does-not-exist")
    assert resp.status_code in (404, 405)
    js = resp.get_json()
    assert js["success"] is False
    assert "error" in js


def test_spa_serving_routes_to_index():
    client = flask_app.test_client()
    r1 = client.get("/")
    assert r1.status_code == 200
    assert b"SpendLens" in r1.data

    r2 = client.get("/someclientroute")
    assert r2.status_code == 200
    assert b"SpendLens" in r2.data

