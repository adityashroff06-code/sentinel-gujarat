"""S2.1 acceptance (timeline half): pure recording-timeline arithmetic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.core import timeline

IST = timezone(timedelta(hours=5, minutes=30))
EPOCH = datetime(2026, 6, 13, 21, 0, 0, tzinfo=IST)


def test_epoch_default():
    assert timeline.recording_epoch() == EPOCH
    assert timeline.loop_seconds() == 43200


def test_position_to_stream_time_wraps():
    assert timeline.position_to_stream_time(0) == EPOCH
    assert timeline.position_to_stream_time(100) == EPOCH + timedelta(seconds=100)
    assert timeline.position_to_stream_time(43200 + 10) == EPOCH + timedelta(seconds=10)


def test_roundtrip():
    for position in (0.0, 1.5, 4321.0, 43199.9):
        ts = timeline.position_to_stream_time(position)
        assert timeline.stream_time_to_position(ts) == round(position % 43200, 6)


def test_live_position_honours_offset_and_loop(monkeypatch):
    monkeypatch.setenv("SENTINEL_PLAYBACK_OFFSET_S", "100")
    assert timeline.live_position(EPOCH) == 100
    assert timeline.live_position(EPOCH + timedelta(seconds=43200)) == 100
    assert timeline.live_position(EPOCH + timedelta(seconds=50)) == 150
