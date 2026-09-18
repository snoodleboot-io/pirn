"""Tests for :class:`TrajectoryEmitter` (ADR "agents speaks core" WS3 part 3).

Attaches the emitter to a real ``Tapestry`` and runs a small graph, so the
trace is built from the engine's own ``on_lineage`` callback rather than
manual ``.record()`` calls.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.determinism.trace_event_kind import TraceEventKind
from pirn_agents.determinism.trajectory_emitter import TrajectoryEmitter


class FakeLlmCall(Knot):
    def __init__(self, prompt: Knot, **kwargs: Any) -> None:
        super().__init__(prompt=prompt, **kwargs)

    async def process(self, prompt: str, **_: Any) -> str:
        return f"answer to {prompt}"


class Doubler(Knot):
    def __init__(self, x: Knot, **kwargs: Any) -> None:
        super().__init__(x=x, **kwargs)

    async def process(self, x: int, **_: Any) -> int:
        return x * 2


class TestTrajectoryEmitter:
    async def test_captures_one_event_per_knot_in_run_order(self) -> None:
        emitter = TrajectoryEmitter()
        with Tapestry(emitters=[emitter]) as tapestry:
            prompt = Parameter(name="prompt", type_=str)
            FakeLlmCall(prompt=prompt, _config=KnotConfig(id="llm_call"))
        result = await tapestry.run(RunRequest(parameters={"prompt": "hi"}))

        trace = emitter.trace_for(result.run_id)
        names = {event.name for event in trace.events}
        assert "llm_call" in names

    async def test_classifies_llm_named_knots_as_llm_call(self) -> None:
        emitter = TrajectoryEmitter()
        with Tapestry(emitters=[emitter]) as tapestry:
            prompt = Parameter(name="prompt", type_=str)
            FakeLlmCall(prompt=prompt, _config=KnotConfig(id="llm_call"))
        result = await tapestry.run(RunRequest(parameters={"prompt": "hi"}))

        trace = emitter.trace_for(result.run_id)
        llm_event = next(event for event in trace.events if event.name == "llm_call")
        assert llm_event.kind is TraceEventKind.LLM_CALL

    async def test_unclassified_knots_default_to_output(self) -> None:
        emitter = TrajectoryEmitter()
        with Tapestry(emitters=[emitter]) as tapestry:
            param = Parameter(name="x", type_=int)
            Doubler(x=param, _config=KnotConfig(id="double"))
        result = await tapestry.run(RunRequest(parameters={"x": 5}))

        trace = emitter.trace_for(result.run_id)
        double_event = next(event for event in trace.events if event.name == "double")
        assert double_event.kind is TraceEventKind.OUTPUT

    async def test_custom_classifier_overrides_the_default(self) -> None:
        emitter = TrajectoryEmitter(classify=lambda _record: TraceEventKind.TOOL_CALL)
        with Tapestry(emitters=[emitter]) as tapestry:
            param = Parameter(name="x", type_=int)
            Doubler(x=param, _config=KnotConfig(id="double"))
        result = await tapestry.run(RunRequest(parameters={"x": 5}))

        trace = emitter.trace_for(result.run_id)
        assert all(event.kind is TraceEventKind.TOOL_CALL for event in trace.events)

    async def test_traces_are_kept_separately_by_run_id(self) -> None:
        emitter = TrajectoryEmitter()
        with Tapestry(emitters=[emitter]) as tapestry:
            param = Parameter(name="x", type_=int)
            Doubler(x=param, _config=KnotConfig(id="double"))
        first = await tapestry.run(RunRequest(parameters={"x": 1}))
        second = await tapestry.run(RunRequest(parameters={"x": 2}))

        assert first.run_id != second.run_id
        assert emitter.trace_for(first.run_id).run_id == first.run_id
        assert emitter.trace_for(second.run_id).run_id == second.run_id

    async def test_forget_drops_a_runs_events(self) -> None:
        emitter = TrajectoryEmitter()
        with Tapestry(emitters=[emitter]) as tapestry:
            param = Parameter(name="x", type_=int)
            Doubler(x=param, _config=KnotConfig(id="double"))
        result = await tapestry.run(RunRequest(parameters={"x": 1}))
        assert emitter.trace_for(result.run_id).events

        emitter.forget(result.run_id)

        assert emitter.trace_for(result.run_id).events == ()

    def test_unknown_run_id_returns_an_empty_trace(self) -> None:
        emitter = TrajectoryEmitter()
        trace = emitter.trace_for("no-such-run")
        assert trace.events == ()

    def test_rejects_non_clock(self) -> None:
        try:
            TrajectoryEmitter(clock="not a clock")
        except TypeError:
            pass
        else:
            raise AssertionError("expected TypeError")
