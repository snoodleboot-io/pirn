"""Mirrored tests for structured trajectory capture (F29-S3)."""

from __future__ import annotations

import unittest

from pirn_agents.determinism.run_trace import RunTrace
from pirn_agents.determinism.trace_event import TraceEvent
from pirn_agents.determinism.trace_event_kind import TraceEventKind


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


if __name__ == "__main__":
    unittest.main()
