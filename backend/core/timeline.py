"""Recording-timeline arithmetic (decisions F13, F29) — pure functions.

The sandbox recordings loop (~12 h) on one shared timeline. The epoch is a
**demo constant** anchoring the recordings' burned-in clock for display and
harvest alignment — never presented as a measurement. Positions are seconds
into the loop; stream times are timezone-aware datetimes.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from backend.core import config


def recording_epoch() -> datetime:
    """The configured epoch as an aware datetime (default IST-anchored)."""
    return datetime.fromisoformat(config.recording_epoch())


def loop_seconds() -> int:
    return config.loop_seconds()


def position_to_stream_time(offset_s: float) -> datetime:
    """Stream-time instant for a position (seconds into the loop)."""
    return recording_epoch() + timedelta(seconds=offset_s % loop_seconds())


def stream_time_to_position(ts: datetime) -> float:
    """Seconds into the loop for a stream-time instant."""
    return (ts - recording_epoch()).total_seconds() % loop_seconds()


def live_position(now: datetime) -> float:
    """The shared 'live' loop position at wall-clock *now*, honouring
    SENTINEL_PLAYBACK_OFFSET_S (≈34000 puts the HLS live edge in daylight)."""
    elapsed = (now - recording_epoch()).total_seconds() + config.playback_offset_s()
    return elapsed % loop_seconds()
