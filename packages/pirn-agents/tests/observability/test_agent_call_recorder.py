"""Tests for :class:`AgentCallRecorder` — the emitter-path call observer.

Written in the project's ``asyncio_mode = "auto"`` style (module-level
``async def test_...`` functions) for the run-scoped cases, plus one plain
``unittest.IsolatedAsyncioTestCase`` for the outside-a-run no-op, matching how
``test_current_run_id.py`` (core) is split.
"""

from __future__ import annotations

import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.emitters.emitter import Emitter
from pirn.managers.knot_state import KnotState
from pirn.managers.status_event import StatusEvent
from pirn.tapestry import Tapestry

from pirn_agents.observability.agent_call_recorder import AgentCallRecorder


class _CapturingEmitter(Emitter):
    def __init__(self) -> None:
        self.statuses: list[StatusEvent] = []

    async def on_status(self, event: StatusEvent) -> None:
        self.statuses.append(event)


def _agent_events(emitter: _CapturingEmitter) -> list[StatusEvent]:
    """Events our own recorder produced, filtered out of the engine's own."""
    return [e for e in emitter.statuses if e.extra]


class OutsideARunTests(unittest.IsolatedAsyncioTestCase):
    async def test_record_is_a_noop_outside_a_run(self) -> None:
        emitter = _CapturingEmitter()
        # `record` only reads the ambient run; with none in flight (and
        # `emitter` never subscribed to anything) this must not raise and
        # must deliver nothing anywhere.
        await AgentCallRecorder.record(knot_id="k1", kind="llm", ok=True, latency=0.1)
        assert emitter.statuses == []


class _LLMCallKnot(Knot):
    """A minimal stand-in for a pattern's LLM-call sub-step.

    Not a production knot — just enough to prove `AgentCallRecorder` works
    from inside a real engine-scheduled `process()`, the same shape a real
    LLM-call knot would use.
    """

    async def process(self, **_: object) -> str:
        await AgentCallRecorder.record(
            knot_id=self.knot_id,
            kind="llm",
            ok=True,
            latency=0.05,
            model="test-model",
            tokens=17,
        )
        return "reply"


async def test_record_success_emits_succeeded_event_with_extra() -> None:
    emitter = _CapturingEmitter()
    with Tapestry(emitters=[emitter]) as t:
        node = _LLMCallKnot(_config=KnotConfig(id="llm"))

    result = await t.run(RunRequest(), terminals=node)

    assert result.succeeded
    events = _agent_events(emitter)
    assert len(events) == 1
    event = events[0]
    assert event.knot_id == "llm"
    assert event.run_id == result.run_id
    assert event.state is KnotState.SUCCEEDED
    assert event.extra["kind"] == "llm"
    assert event.extra["model"] == "test-model"
    assert event.extra["tokens"] == 17
    assert event.extra["latency"] == 0.05


class _FailingCallKnot(Knot):
    async def process(self, **_: object) -> str:
        await AgentCallRecorder.record(
            knot_id=self.knot_id,
            kind="tool",
            ok=False,
            latency=0.01,
            detail="boom",
            tool_name="search",
        )
        return "value despite the recorded failure"


async def test_record_failure_emits_failed_event() -> None:
    emitter = _CapturingEmitter()
    with Tapestry(emitters=[emitter]) as t:
        node = _FailingCallKnot(_config=KnotConfig(id="tool-call"))

    await t.run(RunRequest(), terminals=node)

    events = _agent_events(emitter)
    assert len(events) == 1
    assert events[0].state is KnotState.FAILED
    assert events[0].detail == "boom"
    assert events[0].extra["kind"] == "tool"
    assert events[0].extra["tool_name"] == "search"


async def test_record_reaches_multiple_emitters() -> None:
    first, second = _CapturingEmitter(), _CapturingEmitter()
    with Tapestry(emitters=[first, second]) as t:
        node = _LLMCallKnot(_config=KnotConfig(id="llm"))

    await t.run(RunRequest(), terminals=node)

    assert len(_agent_events(first)) == 1
    assert len(_agent_events(second)) == 1


async def test_multiple_calls_in_one_knot_share_knot_id() -> None:
    """One knot making several calls reports one event per call, same knot_id."""

    class _TwoCallsKnot(Knot):
        async def process(self, **_: object) -> str:
            await AgentCallRecorder.record(
                knot_id=self.knot_id, kind="retrieval", ok=True, latency=0.01
            )
            await AgentCallRecorder.record(knot_id=self.knot_id, kind="llm", ok=True, latency=0.02)
            return "done"

    emitter = _CapturingEmitter()
    with Tapestry(emitters=[emitter]) as t:
        node = _TwoCallsKnot(_config=KnotConfig(id="combined"))

    await t.run(RunRequest(), terminals=node)

    events = _agent_events(emitter)
    assert len(events) == 2
    assert {e.knot_id for e in events} == {"combined"}
    assert {e.extra["kind"] for e in events} == {"retrieval", "llm"}


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
