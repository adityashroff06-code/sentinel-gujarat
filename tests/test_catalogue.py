"""S3.7: the catalogue adapter accepts both published shapes (decision F45).

The recorded ``/api/ingest`` fixture is written from the Integrator's
Guide's documented fields (id, location, codec, live status, stream
properties, RTSP/WHEP/HLS URLs — ``docs/reference/hackathon-brief.md``
§10), with grid-published department/coordinates on two entries because
that is the case the runbook anticipates. The sandbox shape is the
committed ``data/cameras_raw.json`` itself.
"""

from __future__ import annotations

import json

import pytest

from backend.core import config
from backend.tools import probe, seed_registry

FIXTURE = config.REPO_ROOT / "tests" / "fixtures" / "ingest_catalogue.json"
SANDBOX = config.REPO_ROOT / "data" / "cameras_raw.json"

REGISTRY_COLUMNS = {
    "camera_id", "department", "location_name", "lat", "lon", "codec",
    "width", "height", "declared_fps", "bitrate_kbps", "hls_url",
    "rtsp_url_template", "whep_url_template", "health",
}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _by_id(records):
    return {r["camera_id"]: r for r in records}


def test_both_shapes_normalise_to_the_same_registry_columns():
    sandbox_raw, ingest_raw = _load(SANDBOX), _load(FIXTURE)
    assert probe.catalogue_shape(sandbox_raw) == "cameras.json"
    assert probe.catalogue_shape(ingest_raw) == "ingest"

    sandbox = probe.normalise_catalogue(sandbox_raw)
    ingest = probe.normalise_catalogue(ingest_raw)
    assert len(sandbox) == 30 and len(ingest) == 3
    for rec in [*sandbox, *ingest]:
        assert set(rec) <= REGISTRY_COLUMNS
        assert rec["camera_id"] and rec["location_name"]

    # cameras.json supplies id + name only — nothing else may be invented
    assert sandbox[0] == {"camera_id": "cam01",
                          "location_name": "01 Chiman bhai Bridge"}

    ingest = _by_id(ingest)
    cam06 = ingest["cam06"]
    assert cam06["department"] == "Municipal"
    assert cam06["codec"] == "h264"          # "H.264" folded to the contract
    assert cam06["health"] == "online" and cam06["declared_fps"] == 25.0
    assert cam06["lat"] == pytest.approx(21.4931)
    cam09 = ingest["cam09"]
    assert cam09["health"] == "offline" and cam09["codec"] == "hevc"
    assert "department" not in cam09         # absent, not null
    cam31 = ingest["cam31"]                  # synonym spellings normalise too
    assert cam31["declared_fps"] == 30.0 and cam31["bitrate_kbps"] == 1200
    assert cam31["health"] == "online" and cam31["lat"] == pytest.approx(23.2231)
    assert cam31["hls_url"].endswith("/stream/cam31/index.m3u8")


def test_catalogue_urls_never_store_credentials():
    ingest = _by_id(probe.normalise_catalogue(_load(FIXTURE)))
    assert ingest["cam09"]["rtsp_url_template"] == (
        "rtsp://<email>:<password>@sandbox.example:8554/stream/cam09"
    )
    assert "not-a-real-secret" not in json.dumps(list(ingest.values()))
    # a URL without userinfo passes through verbatim
    assert ingest["cam06"]["rtsp_url_template"] == (
        "rtsp://sandbox.example:8554/stream/cam06"
    )


def test_fetch_catalogue_local_override_no_network_no_rewrite(monkeypatch):
    committed = SANDBOX.read_bytes()
    monkeypatch.setenv("SENTINEL_CATALOGUE_URL", str(FIXTURE))
    records = probe.fetch_catalogue()  # no session, no network
    assert [r["camera_id"] for r in records] == ["cam06", "cam09", "cam31"]
    # a local-file source never rewrites the committed sandbox catalogue
    assert SANDBOX.read_bytes() == committed


def test_ingest_shape_flows_through_seed_registry_and_wins_over_seed(
        con, monkeypatch):
    monkeypatch.setenv("SENTINEL_CATALOGUE_URL", str(FIXTURE))
    assert seed_registry.upsert_catalogue(con) == 3
    applied = seed_registry.apply_seed(con)
    con.commit()
    assert applied == 2  # only cam06/cam09 exist in both catalogue and seed

    rows = {r["camera_id"]: r
            for r in con.execute("SELECT * FROM cameras").fetchall()}
    # a camera absent from the catalogue is never invented
    assert set(rows) == {"cam06", "cam09", "cam31"}

    # catalogue-supplied department and location win over the seed
    assert rows["cam06"]["department"] == "Municipal"  # seed says GSRTC
    assert rows["cam06"]["location_name"] == "Timbavadi Gate Plaza (grid-published)"
    assert rows["cam06"]["lat"] == pytest.approx(21.4931)  # seed says 21.4922
    # the seed fills only what the catalogue did not carry
    assert rows["cam09"]["department"] == "Police"     # from the seed
    assert rows["cam09"]["location_name"] == "New Bypass Circle (grid-published)"
    assert rows["cam06"]["fps_tier"] == "active"       # tier stays seed-owned
    assert rows["cam31"]["department"] == "Police"     # grid-published, no seed row
    assert rows["cam31"]["fps_tier"] == "registered"   # schema default
    # live status flowed into health; stream facts stored
    assert rows["cam06"]["health"] == "online"
    assert rows["cam09"]["health"] == "offline"
    assert rows["cam31"]["codec"] == "h264" and rows["cam31"]["width"] == 2560
    for row in rows.values():
        assert row["source"] == "catalogue" and row["transport"] == "none"

    # idempotent: a second pass leaves the same rows
    seed_registry.upsert_catalogue(con)
    seed_registry.apply_seed(con)
    con.commit()
    again = {r["camera_id"]: r
             for r in con.execute("SELECT * FROM cameras").fetchall()}
    assert {k: v["department"] for k, v in again.items()} == \
           {k: v["department"] for k, v in rows.items()}
    assert again["cam06"]["location_name"] == rows["cam06"]["location_name"]


def test_sandbox_shape_unchanged_seed_fills_the_gaps(con, monkeypatch):
    monkeypatch.delenv("SENTINEL_CATALOGUE_URL", raising=False)
    assert seed_registry.upsert_catalogue(con) == 30
    assert seed_registry.apply_seed(con) == 30
    con.commit()
    assert seed_registry.summarise(con) == (30, 5, 5, True)
    row = con.execute(
        "SELECT * FROM cameras WHERE camera_id = 'cam06'").fetchone()
    # catalogue-supplied name kept verbatim; seed fills the rest
    assert row["location_name"] == "06 Timbavadi gate-Junagadh"
    assert row["department"] == "GSRTC" and row["fps_tier"] == "active"
    assert row["lat"] == pytest.approx(21.4922)
