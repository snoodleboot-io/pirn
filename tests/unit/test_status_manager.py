"""StatusManager tests."""

from __future__ import annotations

from pirn.managers.status import KnotState, StatusManager


def test_initial_state_is_pending():
    sm = StatusManager(run_id="r")
    assert sm.get("k1") is KnotState.PENDING


def test_transition_records_state():
    sm = StatusManager(run_id="r")
    sm.transition("k1", KnotState.RUNNING)
    assert sm.get("k1") is KnotState.RUNNING
    sm.transition("k1", KnotState.SUCCEEDED)
    assert sm.get("k1") is KnotState.SUCCEEDED


def test_events_recorded_in_order():
    sm = StatusManager(run_id="r")
    sm.transition("k1", KnotState.RUNNING)
    sm.transition("k1", KnotState.SUCCEEDED)
    sm.transition("k2", KnotState.RUNNING)
    events = sm.events()
    assert [e.knot_id for e in events] == ["k1", "k1", "k2"]
    assert [e.state for e in events] == [
        KnotState.RUNNING,
        KnotState.SUCCEEDED,
        KnotState.RUNNING,
    ]


def test_snapshot_reflects_latest():
    sm = StatusManager(run_id="r")
    sm.transition("k1", KnotState.RUNNING)
    sm.transition("k2", KnotState.SKIPPED)
    snap = sm.snapshot()
    assert snap == {"k1": KnotState.RUNNING, "k2": KnotState.SKIPPED}


def test_subscriber_receives_events():
    sm = StatusManager(run_id="r")
    received = []
    sm.subscribe(lambda e: received.append((e.knot_id, e.state)))
    sm.transition("k1", KnotState.RUNNING)
    sm.transition("k2", KnotState.FAILED)
    assert received == [
        ("k1", KnotState.RUNNING),
        ("k2", KnotState.FAILED),
    ]


def test_subscriber_exception_is_swallowed():
    """A bad subscriber must not break the run."""
    sm = StatusManager(run_id="r")

    def bad(_event):
        raise RuntimeError("subscriber error")

    sm.subscribe(bad)
    # Should not raise.
    sm.transition("k1", KnotState.RUNNING)
    assert sm.get("k1") is KnotState.RUNNING


def test_transition_with_detail():
    sm = StatusManager(run_id="r")
    sm.transition("k1", KnotState.SKIPPED, detail="branch_not_selected")
    events = sm.events()
    assert events[0].detail == "branch_not_selected"
