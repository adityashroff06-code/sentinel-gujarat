"""S2.3 acceptance: greedy IoU + centre-distance tracker (docs/tasks.md)."""

from __future__ import annotations

import pytest

from ml.anpr.detect import Detection, superclass
from ml.anpr.track import Tracker


def det(x: float, y: float, w: float = 100.0, h: float = 60.0,
        cls: str = "car", conf: float = 0.9) -> Detection:
    return Detection(cls=cls, superclass=superclass(cls), conf=conf,
                     xyxy=(x, y, x + w, y + h))


def test_one_id_across_30_moving_frames() -> None:
    tracker = Tracker()
    ids = set()
    for i in range(30):
        matches = tracker.update([det(50 + i * 10, 100)], pts_ms=i * 333.0)
        assert len(matches) == 1
        ids.add(matches[0][0].id)
    assert len(ids) == 1
    (track,) = tracker.tracks.values()
    assert track.hits == 30


def test_one_id_across_a_car_truck_class_flip() -> None:
    tracker = Tracker()
    ids = set()
    for i in range(30):
        cls = "car" if i < 15 else "truck"
        matches = tracker.update([det(50 + i * 10, 100, cls=cls)], pts_ms=i * 333.0)
        ids.add(matches[0][0].id)
    assert len(ids) == 1
    (track,) = tracker.tracks.values()
    assert track.superclass == "vehicle" and track.cls == "truck"


def test_different_superclasses_never_merge() -> None:
    tracker = Tracker()
    matches = tracker.update([det(50, 100, cls="car")], pts_ms=0.0)
    car_id = matches[0][0].id
    matches = tracker.update([det(55, 102, cls="person")], pts_ms=333.0)
    assert matches[0][0].id != car_id


def test_track_ages_out_and_ids_are_never_reused() -> None:
    tracker = Tracker(max_age_s=3.0)
    first = tracker.update([det(50, 100)], pts_ms=0.0)[0][0].id
    # 4 s later (> max_age): the old track is gone, a NEW id is issued.
    second = tracker.update([det(50, 100)], pts_ms=4000.0)[0][0].id
    assert second != first and second > first


def test_reset_clears_tracks_but_not_the_id_counter() -> None:
    tracker = Tracker()
    first = tracker.update([det(50, 100)], pts_ms=0.0)[0][0].id
    tracker.reset()
    assert tracker.tracks == {}
    second = tracker.update([det(50, 100)], pts_ms=333.0)[0][0].id
    assert second > first


def test_velocity_from_pts_deltas() -> None:
    tracker = Tracker()
    tracker.update([det(100, 100)], pts_ms=0.0)
    (track, _), = tracker.update([det(110, 100)], pts_ms=1000.0)
    assert track.velocity[0] == pytest.approx(10.0)  # px/s along +x
    assert track.velocity[1] == pytest.approx(0.0)


def test_two_vehicles_keep_separate_ids() -> None:
    tracker = Tracker()
    for i in range(10):
        matches = tracker.update(
            [det(50 + i * 10, 100), det(500 - i * 10, 300)], pts_ms=i * 333.0)
        assert len({t.id for t, _ in matches}) == 2
    assert len(tracker.tracks) == 2
