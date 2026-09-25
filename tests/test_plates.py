"""S1.2 acceptance: table-driven grammar/matching tests + the matcher probe."""

from __future__ import annotations

import time

import pytest

from backend.core import matcher as matchermod
from backend.core import plates


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("GJ32 K 9819", "GJ32K9819"),
        ("gj-01 ab 1234", "GJ01AB1234"),
        ("GJ01AB1234", "GJ01AB1234"),
        (" 22 BH 1234 AA ", "22BH1234AA"),
    ],
)
def test_normalise(raw, expected):
    assert plates.normalise(raw) == expected


@pytest.mark.parametrize(
    ("letter", "digit"),
    [("O", "0"), ("I", "1"), ("S", "5"), ("B", "8"), ("Z", "2"), ("G", "6"), ("Q", "0")],
)
def test_each_ambiguity_pair_folds(letter, digit):
    assert plates.canonical(letter) == digit
    assert plates.canonical(digit) == digit


@pytest.mark.parametrize(
    ("s", "expected"),
    [
        ("GJ01AB1234", "full"),          # standard
        ("22BH1234AA", "full"),          # BH-series
        ("GJ32K9819", "full"),           # single-letter series
        ("GJ32 K 9819", "full"),         # normalised inside
        ("GJ01AB12O4", "full"),          # O coerced to 0 where a digit is expected
        ("6J01AB1234", "full"),          # 6 coerced to G where a letter is expected
        ("GJ05JB432", "partial"),        # structural prefix, length 9
        ("GJ01", "partial"),             # minimum-length prefix
        ("GJ0", None),                   # too short for partial
        ("OADFIX2FR", None),             # caption junk
        ("DFIX2F", None),
        ("XX01AB1234", None),            # state code not in the whitelist
        ("", None),
    ],
)
def test_plate_like(s, expected):
    assert plates.plate_like(s) == expected


def test_is_partial():
    assert plates.is_partial("GJ05JB432")
    assert not plates.is_partial("GJ01AB1234")


# --- coerce: the stored form of a full read (ANPR lane, 25 Sep) ------------
# Observed on the live DB on 25 Sep: the OCR confusion and the clean read of
# one registration were stored as two plates, so search and dedupe saw two.

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("6J23H1548", "GJ23H1548"),      # observed: 6 where the state letter G belongs
        ("GJ1157924", "GJ11S7924"),      # observed: 5 where the series letter S belongs
        ("GJO3XH0407", "GJ03XH0407"),    # observed: O where the district digit 0 belongs
    ],
    ids=["observed_6J23H1548", "observed_GJ1157924", "observed_GJO3XH0407"],
)
def test_coerce_resolves_observed_ocr_confusions(raw, expected):
    assert plates.coerce(raw) == expected
    # the stored form is one plate with its OCR twin: canonical never moves
    assert plates.canonical(expected) == plates.canonical(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("GJ01AB1234", "GJ01AB1234"),    # already valid: unchanged
        ("gj 01 ab 1234", "GJ01AB1234"), # normalised first
        ("22BH1234AA", "22BH1234AA"),    # BH-series, valid
        ("228H06418", "22BH0641B"),      # BH-series, 8->B in the literal and the letter
        ("GJ01AB12O4", "GJ01AB1204"),    # O->0 in the number
        ("GJ05JB432", None),             # partial (F40): never coerced to a registration
        ("GJ01", None),                  # partial prefix
        ("OADFIX2FR", None),             # rejected
        ("", None),
    ],
)
def test_coerce_table(raw, expected):
    assert plates.coerce(raw) == expected


def test_coerce_never_changes_canonical():
    for raw in ("6J23H1548", "GJ1157924", "GJO3XH0407", "MHO1DE2432", "6J118R8190",
                "228H06418", "GJ01A81234", "6J03P02863", "GJ01AB1234"):
        coerced = plates.coerce(raw)
        assert coerced is not None, raw
        assert plates.canonical(coerced) == plates.canonical(raw), raw
        assert plates.plate_like(coerced) == "full"
        assert plates.coerce(coerced) == coerced          # idempotent


@pytest.mark.parametrize(
    ("a", "b", "matched", "distance", "rule"),
    [
        ("GJ01AB1234", "GJ01AB1234", True, 0.0, "exact"),
        ("GJ01AB1234", "GJ01A81234", True, 0.0, "ambiguity"),   # B <-> 8
        ("GJ01AB1234", "GJ01AB1235", True, 1.0, "fuzzy"),       # neighbour registration
        ("GJ05JB432", "GJ05JB4321", False, 1.0, "none"),        # partial never fuzzy-matches
        ("GJ01AB1234", "MH01AB1234", False, 2.0, "none"),
    ],
)
def test_plate_match_table(a, b, matched, distance, rule):
    got_matched, got_distance, got_rule = plates.plate_match(a, b)
    assert (got_matched, got_rule) == (matched, rule)
    assert got_distance == pytest.approx(distance)


def test_weighted_distance_composes():
    # B->8 is an in-class substitution (0.25); 4->5 is a real one (1.0).
    # Together they exceed the 1.0 fuzzy ceiling, so this is NOT a match —
    # the cheap class substitution alone must not open the fuzzy door.
    matched, distance, rule = plates.plate_match("GJ01AB1234", "GJ01A81235")
    assert (matched, rule) == (False, "none")
    assert distance == pytest.approx(1.25)


def test_fuzzy_not_alertable_by_default(monkeypatch):
    monkeypatch.delenv("SENTINEL_ALERT_ON_FUZZY", raising=False)
    assert plates.alertable("exact")
    assert plates.alertable("ambiguity")
    assert not plates.alertable("fuzzy")
    assert not plates.alertable("none")
    monkeypatch.setenv("SENTINEL_ALERT_ON_FUZZY", "true")
    assert plates.alertable("fuzzy")


def _seed_watchlist(con, n: int) -> None:
    from backend.core import db as dbmod

    now = dbmod.utcnow()
    rows = []
    for i in range(n):
        plate = f"GJ{i % 39 + 1:02d}A{chr(65 + i % 26)}{i % 10000:04d}"
        rows.append((plate, plates.canonical(plate), "suspect", "low", now))
    rows.append(("GJ01AB1234", plates.canonical("GJ01AB1234"), "stolen_vehicle", "high", now))
    con.executemany(
        "INSERT OR IGNORE INTO watchlist (plate, plate_canonical, category, severity, added_at)"
        " VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    con.commit()


def test_matcher_exact_probe_under_5ms(con):
    _seed_watchlist(con, 1000)
    cache = matchermod.WatchlistCache()
    count = cache.refresh(con)
    assert count >= 1000
    start = time.perf_counter()
    hit = cache.find_match("GJ01A81234")   # ambiguity probe through the canonical index
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert hit is not None
    row, rule, distance = hit
    assert row["plate"] == "GJ01AB1234" and rule == "ambiguity" and distance == 0.0
    assert elapsed_ms < 5, f"index probe took {elapsed_ms:.2f} ms"


def test_matcher_fuzzy_and_partial(con):
    _seed_watchlist(con, 50)
    cache = matchermod.WatchlistCache()
    cache.refresh(con)
    hit = cache.find_match("GJ01AB1235")   # neighbour of the seeded hero plate
    assert hit is not None and hit[1] == "fuzzy" and hit[2] == pytest.approx(1.0)
    assert not matchermod.alertable(hit[1])          # F21 default
    assert cache.find_match("GJ05JB432") is None     # partial: no fuzzy path


def test_matcher_skips_expired_rows(con):
    from backend.core import db as dbmod

    now = dbmod.utcnow()
    con.execute(
        "INSERT INTO watchlist (plate, plate_canonical, category, severity, added_at, expires_at)"
        " VALUES ('GJ09ZZ9999', ?, 'blacklisted', 'low', ?, '2000-01-01T00:00:00+00:00')",
        (plates.canonical("GJ09ZZ9999"), now),
    )
    con.commit()
    cache = matchermod.WatchlistCache()
    cache.refresh(con)
    assert cache.find_match("GJ09ZZ9999") is None
