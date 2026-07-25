"""Mirrored tests for time-travel inspect + run diff (F29-S4)."""

from __future__ import annotations

import unittest

from pirn_agents.determinism.frozen_clock import FrozenClock
from pirn_agents.determinism.run_trace import RunTrace
from pirn_agents.determinism.trace_differ import TraceDiffer
from pirn_agents.determinism.trace_event_kind import TraceEventKind
from pirn_agents.determinism.trace_inspector import TraceInspector
from pirn_agents.determinism.trajectory_recorder import TrajectoryRecorder


def _trace(run_id: str, answer: str, *, steps: int = 3) -> RunTrace:
    recorder = TrajectoryRecorder(run_id=run_id, clock=FrozenClock())
    recorder.record(kind=TraceEventKind.INPUT, name="prompt", payload={"q": "hi"})
    for i in range(steps - 2):
        recorder.record(kind=TraceEventKind.TOOL_CALL, name="search", payload={"i": i})
    recorder.record(kind=TraceEventKind.OUTPUT, name="answer", payload={"a": answer})
    return recorder.snapshot()


class TraceInspectorTests(unittest.TestCase):
    def test_steps_forward_through_events(self) -> None:
        inspector = TraceInspector(_trace("r", "yes"))
        assert inspector.step_count == 3
        seen = []
        while inspector.has_next:
            event = inspector.step()
            assert event is not None
            seen.append(event.index)
        assert seen == [0, 1, 2]
        assert inspector.step() is None

    def test_reset_rewinds(self) -> None:
        inspector = TraceInspector(_trace("r", "yes"))
        inspector.step()
        inspector.reset()
        assert inspector.position == 0

    def test_event_at_random_access(self) -> None:
        inspector = TraceInspector(_trace("r", "yes"))
        assert inspector.event_at(0).kind is TraceEventKind.INPUT
        with self.assertRaises(IndexError):
            inspector.event_at(99)

    def test_events_of_kind_filters(self) -> None:
        inspector = TraceInspector(_trace("r", "yes"))
        assert len(inspector.events_of_kind(TraceEventKind.OUTPUT)) == 1

    def test_rejects_non_trace(self) -> None:
        with self.assertRaises(TypeError):
            TraceInspector(object())  # type: ignore[arg-type]


class TraceDifferTests(unittest.TestCase):
    def test_identical_traces_have_no_diff(self) -> None:
        diff = TraceDiffer().diff(_trace("a", "yes"), _trace("b", "yes"))
        assert diff.is_identical

    def test_changed_output_is_flagged(self) -> None:
        diff = TraceDiffer().diff(_trace("a", "yes"), _trace("b", "no"))
        assert not diff.is_identical
        assert len(diff.changed) == 1
        entry = diff.changed[0]
        assert entry["index"] == 2
        assert entry["fields"] == ["payload"]

    def test_length_difference_reports_added(self) -> None:
        diff = TraceDiffer().diff(_trace("a", "yes", steps=3), _trace("b", "yes", steps=5))
        assert diff.added == (3, 4)
        assert diff.removed == ()

    def test_diff_round_trips(self) -> None:
        from pirn_agents.determinism.trace_diff import TraceDiff

        diff = TraceDiffer().diff(_trace("a", "yes"), _trace("b", "no"))
        assert TraceDiff.from_payload(diff.to_payload()) == diff

    def test_rejects_non_trace(self) -> None:
        with self.assertRaises(TypeError):
            TraceDiffer().diff(_trace("a", "yes"), object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
