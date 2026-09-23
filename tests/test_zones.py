"""S2.5 acceptance: zone confirmation, line direction, zone alerts (docs/tasks.md)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.core.alerts import create_alert
from backend.core.db import utcnow
from ml.analytics.events import insert_zone_event
from ml.analytics.zones import ZoneMonitor, parse_zones, validate_zone

T0 = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)

SQUARE = {"zone_id": "z1", "name": "Yard", "type": "intrusion", "severity": "high",
          "points": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]}
LINE = {"zone_id": "z2", "name": "Exit lane", "type": "line", "severity": "medium",
        "points": [[0.0, 0.5], [1.0, 0.5]]}

IN = (0.5, 0.5)
OUT = (0.9, 0.9)


def _monitor(*zones) -> ZoneMonitor:
    import json

    return ZoneMonitor(parse_zones(json.dumps(list(zones))))


def _fires(monitor: ZoneMonitor, track_id: int, footprints) -> int:
    return sum(len(monitor.update(track_id, foot)) for foot in footprints)


def test_validate_rejects_bad_shapes() -> None:
    assert validate_zone({**SQUARE, "points": [[0, 0], [1, 1]]}) is not None  # < 3
    assert validate_zone({**LINE, "points": [[0, 0.5]]}) is not None          # != 2
    assert validate_zone({**LINE, "points": [[0, 0.5], [1, 0.5], [1, 1]]}) is not None
    assert validate_zone({**SQUARE, "type": "banana"}) is not None
    assert validate_zone({**SQUARE, "severity": "extreme"}) is not None
    assert validate_zone(SQUARE) is None and validate_zone(LINE) is None


def test_parse_zones_drops_invalid_entries() -> None:
    import json

    zones = parse_zones(json.dumps([SQUARE, {"zone_id": "bad", "type": "line",
                                             "severity": "low", "points": [[0, 0]]}]))
    assert [z.zone_id for z in zones] == ["z1"]
    assert parse_zones(None) == [] and parse_zones("not json") == []


def test_intrusion_fires_once_after_two_consecutive_inside_frames() -> None:
    monitor = _monitor(SQUARE)
    assert _fires(monitor, 1, [IN]) == 0                      # 1 frame: unconfirmed
    assert _fires(monitor, 1, [IN]) == 1                      # 2nd consecutive: fires
    assert _fires(monitor, 1, [IN, IN, IN]) == 0              # once per track


def test_one_bad_frame_still_fires_exactly_once() -> None:
    # inside, inside, outside, inside -> exactly one fire (on frame 2).
    monitor = _monitor(SQUARE)
    assert _fires(monitor, 1, [IN, IN, OUT, IN]) == 1


def test_single_frame_blips_never_fire() -> None:
    # inside, outside, outside -> never.
    monitor = _monitor(SQUARE)
    assert _fires(monitor, 1, [IN, OUT, OUT]) == 0
    # And a flapping box never fires either.
    assert _fires(monitor, 2, [IN, OUT, IN, OUT, IN, OUT]) == 0


def test_two_tracks_fire_independently() -> None:
    monitor = _monitor(SQUARE)
    assert _fires(monitor, 1, [IN, IN]) == 1
    assert _fires(monitor, 2, [IN, IN]) == 1


def test_line_cross_fires_downward_only() -> None:
    above, below = (0.5, 0.3), (0.5, 0.7)
    monitor = _monitor(LINE)
    # Confirmed above (2 frames), then confirmed below (2 frames): one fire.
    assert _fires(monitor, 1, [above, above, below]) == 0     # below unconfirmed
    assert _fires(monitor, 1, [below]) == 1                   # confirmed: fires
    # Crossing back up never fires.
    assert _fires(monitor, 1, [above, above]) == 0
    # A fresh track going up: never.
    assert _fires(monitor, 2, [below, below, above, above]) == 0


def test_one_bad_side_frame_does_not_cross() -> None:
    above, below = (0.5, 0.3), (0.5, 0.7)
    monitor = _monitor(LINE)
    assert _fires(monitor, 1, [above, above, below, above, above]) == 0


def test_vertical_line_never_fires() -> None:
    vertical = {**LINE, "points": [[0.5, 0.0], [0.5, 1.0]]}
    monitor = _monitor(vertical)
    assert _fires(monitor, 1, [(0.3, 0.5), (0.3, 0.5), (0.7, 0.5), (0.7, 0.5)]) == 0


def test_hot_reload_keeps_state_for_surviving_zones() -> None:
    import json

    monitor = _monitor(SQUARE)
    _fires(monitor, 1, [IN, IN])                              # fired for z1
    monitor.set_zones(parse_zones(json.dumps([SQUARE, LINE])))
    assert _fires(monitor, 1, [IN, IN]) == 0                  # z1 stays fired


# --- zone alerts (kind='zone', §4) -----------------------------------------

@pytest.fixture()
def cam(con):
    con.execute("INSERT INTO cameras (camera_id, created_at, updated_at)"
                " VALUES ('cam09', ?, ?)", (utcnow(), utcnow()))
    con.commit()
    return "cam09"


def test_high_severity_zone_hit_writes_a_zone_alert(con, cam) -> None:
    event = insert_zone_event(
        con, camera_id=cam, zone_id="z1", event_type="intrusion",
        object_class="person", occurred_at=T0, wall_time=T0,
        clock_source="replay", provenance="test")
    con.commit()
    assert event["event_id"] is not None
    alert = create_alert(con, kind="zone", camera_id=cam, severity="high",
                         seen_at=T0, clock_source="replay", event=dict(event))
    con.commit()
    assert alert["kind"] == "zone" and alert["event_id"] == event["event_id"]
    assert alert["zone_id"] == "z1"
    assert alert["sighting_id"] is None and alert["plate"] is None


def test_zone_alert_cooldown_keys_on_zone_and_camera(con, cam) -> None:
    from datetime import timedelta

    def hit(at, zone_id="z1"):
        event = insert_zone_event(
            con, camera_id=cam, zone_id=zone_id, event_type="intrusion",
            object_class="person", occurred_at=at, wall_time=at,
            clock_source="replay", provenance="test")
        alert = create_alert(con, kind="zone", camera_id=cam, severity="high",
                             seen_at=at, clock_source="replay", event=dict(event))
        con.commit()
        return alert

    assert hit(T0) is not None
    assert hit(T0 + timedelta(minutes=2)) is None             # cooldown
    assert hit(T0 + timedelta(minutes=2), zone_id="z9") is not None  # other zone
    assert hit(T0 + timedelta(minutes=6)) is not None         # expired
