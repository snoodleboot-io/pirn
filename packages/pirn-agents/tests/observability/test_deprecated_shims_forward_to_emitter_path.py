"""Prove the deprecated Tracer/Span shims still reach core's emitters.

ADR agents-speaks-core WS4a keeps ``Tracer``/``SpanEmittingToolInvocationHook``
importable for one deprecation cycle, but they are not just inert relics: a
caller that has not migrated yet must still have its telemetry land on the
run's real emitter subscription, through
:class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`,
rather than only the old, disconnected ``ObservabilitySink``.
"""

from __future__ import annotations

import asyncio
import warnings

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.emitters.emitter import Emitter
from pirn.managers.knot_state import KnotState
from pirn.managers.status_event import StatusEvent
from pirn.tapestry import Tapestry

from pirn_agents.observability.observability_sink import ObservabilitySink
from pirn_agents.observability.span_emitting_tool_invocation_hook import (
    SpanEmittingToolInvocationHook,
)
from pirn_agents.observability.tracer import Tracer
from pirn_agents.tools.tool_status import ToolStatus


class _CapturingEmitter(Emitter):
    def __init__(self) -> None:
        self.statuses: list[StatusEvent] = []

    async def on_status(self, event: StatusEvent) -> None:
        self.statuses.append(event)


def _forwarded(emitter: _CapturingEmitter) -> list[StatusEvent]:
    return [e for e in emitter.statuses if e.extra]


class _TracedKnot(Knot):
    """Uses the deprecated Tracer.span() the way an unmigrated caller would."""

    async def process(self, **_: object) -> str:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            tracer = Tracer(ObservabilitySink())
        async with tracer.llm_span(
            name="llm.chat", attributes={"pirn.knot_id": self.knot_id, "model": "m"}
        ):
            pass
        return "done"


async def test_tracer_span_forwards_to_the_runs_emitters() -> None:
    emitter = _CapturingEmitter()
    with Tapestry(emitters=[emitter]) as t:
        node = _TracedKnot(_config=KnotConfig(id="llm"))

    result = await t.run(RunRequest(), terminals=node)

    assert result.succeeded
    forwarded = _forwarded(emitter)
    assert len(forwarded) == 1
    event = forwarded[0]
    assert event.knot_id == "llm"
    assert event.run_id == result.run_id
    assert event.state is KnotState.SUCCEEDED
    assert event.extra["kind"] == "llm"
    assert event.extra["model"] == "m"


async def test_tracer_span_without_a_knot_id_forwards_nothing() -> None:
    """No knot_id supplied — nothing to attribute the event to (documented no-op)."""
    emitter = _CapturingEmitter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        tracer = Tracer(ObservabilitySink())

    with Tapestry(emitters=[emitter]) as t:

        class _Node(Knot):
            async def process(self, **_: object) -> str:
                async with tracer.llm_span(name="llm.chat"):
                    pass
                return "done"

        node = _Node(_config=KnotConfig(id="llm"))

    await t.run(RunRequest(), terminals=node)

    assert _forwarded(emitter) == []


async def test_span_emitting_tool_invocation_hook_forwards_to_the_runs_emitters() -> None:
    emitter = _CapturingEmitter()

    class _HookKnot(Knot):
        async def process(self, **_: object) -> str:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                tracer = Tracer(ObservabilitySink())
                hook = SpanEmittingToolInvocationHook(tracer, knot_id=self.knot_id)
            hook.on_start(tool_name="search", args_digest="d1", call_id="c1")
            hook.on_finish(tool_name="search", call_id="c1", status=ToolStatus.OK, latency=0.1)
            # `on_finish` is synchronous and schedules a fire-and-forget task;
            # give the loop a turn so it actually runs before this knot
            # finishes and the run's emitters are asserted on.
            await asyncio.gather(*hook._pending_tasks)
            return "done"

    with Tapestry(emitters=[emitter]) as t:
        node = _HookKnot(_config=KnotConfig(id="executor"))

    result = await t.run(RunRequest(), terminals=node)

    assert result.succeeded
    forwarded = _forwarded(emitter)
    assert len(forwarded) == 1
    assert forwarded[0].knot_id == "executor"
    assert forwarded[0].extra["kind"] == "tool"
    assert forwarded[0].extra["tool_name"] == "search"


async def test_hook_without_a_knot_id_forwards_nothing() -> None:
    emitter = _CapturingEmitter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        tracer = Tracer(ObservabilitySink())
        hook = SpanEmittingToolInvocationHook(tracer)  # no knot_id

    with Tapestry(emitters=[emitter]) as t:

        class _Node(Knot):
            async def process(self, **_: object) -> str:
                hook.on_start(tool_name="search", args_digest="d1", call_id="c1")
                hook.on_finish(tool_name="search", call_id="c1", status=ToolStatus.OK, latency=0.1)
                return "done"

        node = _Node(_config=KnotConfig(id="executor"))

    await t.run(RunRequest(), terminals=node)

    assert _forwarded(emitter) == []
    assert hook._pending_tasks == []
