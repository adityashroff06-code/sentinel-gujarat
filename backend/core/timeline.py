"""Recording-timeline arithmetic (decision F13/F29) — implemented in S2.1.

This module is a declared stub until task S2.1 builds it: it will expose
``RECORDING_EPOCH``, ``LOOP_SECONDS``, ``position_to_stream_time()``,
``stream_time_to_position()`` and ``live_position()``. Nothing imports it
before S2.1; importing the names below before then raises immediately
rather than returning wrong timestamps.
"""

from __future__ import annotations


def __getattr__(name: str):  # pragma: no cover — replaced by S2.1
    raise NotImplementedError(
        f"backend.core.timeline.{name} is not implemented until task S2.1 (docs/tasks.md)"
    )
