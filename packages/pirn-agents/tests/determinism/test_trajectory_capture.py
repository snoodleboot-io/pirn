"""Mirrored tests for structured trajectory capture (F29-S3)."""

from __future__ import annotations

import unittest

from pirn_agents.determinism.frozen_clock import FrozenClock
from pirn_agents.determinism.run_trace import RunTrace
from pirn_agents.determinism.trace_event import TraceEvent
from pirn_agents.determinism.trace_event_kind import TraceEventKind
from pirn_agents.determinism.trajectory_recorder import TrajectoryRecorder


def _event(index: int = 0) -> TraceEvent:
    return TraceEvent(
        index=index,
        kind=TraceEventKind.TOOL_CALL,
        name="search",
        payload={"q": "hi"},
        timestamp="1970-01-01T00:00:00+00:00",
    )


class TraceEventTests(unittest.TestCase):
    def test_round_trips_without_loss(self) -> None:
        event = _event()
        assert TraceEvent.from_payload(event.to_payload()) == event

    def test_digest_reflects_payload(self) -> None:
        base = _event()
        changed = TraceEvent(
            index=0, kind=base.kind, name=base.name, payload={"q": "bye"}, timestamp=base.timestamp
        )
        assert base.digest != changed.digest

    def test_rejects_negative_index(self) -> None:
        with self.assertRaises(ValueError):
            TraceEvent(index=-1, kind=TraceEventKind.INPUT, name="n", payload=None, timestamp="t")


class RunTraceTests(unittest.TestCase):
    def test_append_only_and_immutable(self) -> None:
        base = RunTrace(run_id="r1")
        extended = base.with_event(_event())
        assert len(base.events) == 0
        assert len(extended.events) == 1

    def test_schema_is_versioned(self) -> None:
        assert RunTrace(run_id="r1").schema_version == "f29-trace/1"

    def test_round_trips_with_metadata(self) -> None:
        trace = RunTrace(run_id="r1", metadata={"seed": 7}).with_event(_event())
        restored = RunTrace.from_payload(trace.to_payload())
        assert restored == trace
        assert restored.metadata["seed"] == 7

    def test_rejects_empty_run_id(self) -> None:
        with self.assertRaises(TypeError):
            RunTrace(run_id="")


class TrajectoryRecorderTests(unittest.TestCase):
    def test_records_ordered_indices_with_injected_clock(self) -> None:
        recorder = TrajectoryRecorder(run_id="r1", clock=FrozenClock(), metadata={"seed": 1})
        recorder.record(kind=TraceEventKind.INPUT, name="prompt", payload={"q": "hi"})
        recorder.record(kind=TraceEventKind.OUTPUT, name="answer", payload={"a": "yo"})
        trace = recorder.snapshot()
        assert [e.index for e in trace.events] == [0, 1]
        assert trace.events[0].timestamp == "1970-01-01T00:00:00+00:00"
        assert trace.metadata == {"seed": 1}

    def test_snapshot_is_a_point_in_time_copy(self) -> None:
        recorder = TrajectoryRecorder(run_id="r1", clock=FrozenClock())
        recorder.record(kind=TraceEventKind.INPUT, name="a", payload=1)
        first = recorder.snapshot()
        recorder.record(kind=TraceEventKind.OUTPUT, name="b", payload=2)
        assert len(first.events) == 1
        assert recorder.event_count == 2

    def test_rejects_non_kind(self) -> None:
        recorder = TrajectoryRecorder(run_id="r1", clock=FrozenClock())
        with self.assertRaises(TypeError):
            recorder.record(kind="input", name="x", payload=None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
