"""S1.3b: seeders are idempotent and CDN-independent (decision F35)."""

from __future__ import annotations

from backend.tools import seed_registry, seed_watchlist


def test_seed_registry_creates_30_rows_from_committed_files(con):
    assert seed_registry.upsert_catalogue(con) == 30
    assert seed_registry.apply_seed(con) == 30
    con.commit()
    total, active, departments, ok = seed_registry.summarise(con)
    assert (total, active, departments, ok) == (30, 5, 5, True)
    # idempotent
    seed_registry.upsert_catalogue(con)
    seed_registry.apply_seed(con)
    con.commit()
    assert seed_registry.summarise(con) == (30, 5, 5, True)


def test_seed_registry_add_and_replay(con):
    seed_registry.upsert_catalogue(con)
    seed_registry.apply_seed(con)
    seed_registry.add_manual(con, "local01", "Municipal",
                             "rtsp://127.0.0.1:8554/stream/local01", "active")
    seed_registry.add_replay(con, "tests/fixtures/synthetic_60s.mp4", ["rep01"])
    con.commit()
    row = con.execute("SELECT * FROM cameras WHERE camera_id = 'local01'").fetchone()
    assert row["transport"] == "rtsp" and row["fps_tier"] == "active" and row["source"] == "manual"
    rep = con.execute("SELECT * FROM cameras WHERE camera_id = 'rep01'").fetchone()
    assert rep["transport"] == "replay" and rep["rtsp_url_template"].endswith(".mp4")
    assert rep["fps_tier"] == "active"  # the soak's supervisor must pick it (S2.5)


def test_seed_watchlist_idempotent_25(con):
    assert seed_watchlist.seed(con) == 25
    con.commit()
    first = con.execute(
        "SELECT plate, category, severity FROM watchlist ORDER BY plate"
    ).fetchall()
    assert len(first) == 25
    seed_watchlist.seed(con)
    con.commit()
    second = con.execute(
        "SELECT plate, category, severity FROM watchlist ORDER BY plate"
    ).fetchall()
    assert [tuple(r) for r in first] == [tuple(r) for r in second]
    hero = con.execute(
        "SELECT category, severity FROM watchlist WHERE plate = 'GJ01AB1234'"
    ).fetchone()
    assert tuple(hero) == ("stolen_vehicle", "high")
    categories = {r[0] for r in con.execute("SELECT DISTINCT category FROM watchlist")}
    assert categories == {"stolen_vehicle", "wanted_person", "missing_person",
                          "blacklisted", "suspect"}
