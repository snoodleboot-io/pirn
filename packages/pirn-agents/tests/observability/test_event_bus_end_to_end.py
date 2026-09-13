"""End-to-end verification: an agent pipeline's LLM/tool calls reach core's
real emitters (ADR agents-speaks-core WS4a, WS4a checkbox 5).

Runs one small pipeline — a stand-in LLM-call knot using
:class:`AgentCallRecorder` directly, plus a real
:class:`~pirn_agents.tools.tool_invocation.ToolInvocation` — twice: once under
``Tapestry(emitters=[OpenTelemetryEmitter(...)])`` and once under
``Tapestry(emitters=[LogEmitter(...)])``, asserting each renders both calls
with ``pirn.run_id``/``pirn.knot_id`` and the agents-domain attributes
(``kind``, ``model``/``tool_name``, ``latency``).
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.emitters.log_emitter import LogEmitter
from pirn.emitters.open_telemetry_emitter import OpenTelemetryEmitter
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry

from pirn_agents.observability.agent_call_recorder import AgentCallRecorder
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation import ToolInvocation


class _FakeOtelSpan:
    def __init__(self, name: str, start_time: int) -> None:
        self.name = name
        self.start_time = start_time
        self.end_time: int | None = None
        self.attributes: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: Any) -> None:
        pass

    def end(self, end_time: int) -> None:
        self.end_time = end_time


class _FakeOtelTracer:
    def __init__(self) -> None:
        self.spans: list[_FakeOtelSpan] = []

    def start_span(self, name: str, start_time: int) -> _FakeOtelSpan:
        span = _FakeOtelSpan(name, start_time)
        self.spans.append(span)
        return span


class _StubTool(Tool):
    """stub search"""

    tool_name: ClassVar[str] = "search"

    def __init__(self, *, q: Knot | str, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(q=q, _config=_config, **kwargs)

    async def process(self, q: str, **_: Any) -> dict[str, int]:
        return {"hits": 3}


class _LLMCallKnot(Knot):
    """Stand-in for a pattern's LLM-call sub-step (see AgentCallRecorder docs)."""

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


class TestOpenTelemetryEmitterRendersAgentCalls:
    async def test_llm_and_tool_calls_produce_spans_with_run_and_knot_id(self) -> None:
        tracer = _FakeOtelTracer()
        with Tapestry(emitters=[OpenTelemetryEmitter(tracer=tracer)]) as t:
            llm = _LLMCallKnot(_config=KnotConfig(id="llm-call"))
            tool = ToolInvocation(
                tool=_StubTool,
                call=ToolCall(tool_name="search", arguments={"q": "hi"}, call_id="c1"),
                _config=KnotConfig(id="tool-call"),
            )
            Aggregator(
                combine=lambda **results: dict(results),
                _config=KnotConfig(id="agg"),
                llm=llm,
                tool=tool,
            )

        result = await t.run(RunRequest())
        assert result.succeeded

        by_name = {s.name: s for s in tracer.spans}
        llm_span = by_name["llm:llm-call"]
        tool_span = by_name["tool:tool-call"]

        assert llm_span.attributes["pirn.run_id"] == result.run_id
        assert llm_span.attributes["pirn.knot_id"] == "llm-call"
        assert llm_span.attributes["agents.model"] == "test-model"
        assert llm_span.attributes["agents.tokens"] == 17
        assert llm_span.end_time is not None

        assert tool_span.attributes["pirn.run_id"] == result.run_id
        assert tool_span.attributes["pirn.knot_id"] == "tool-call"
        assert tool_span.attributes["agents.tool_name"] == "search"
        assert tool_span.attributes["agents.call_id"] == "c1"


class TestLogEmitterLogsAgentCalls:
    async def test_llm_and_tool_calls_are_logged_with_agents_extra(self, caplog) -> None:
        logger = logging.getLogger("test.ws4a.event_bus")
        emitter = LogEmitter(logger=logger)
        with Tapestry(emitters=[emitter]) as t:
            llm = _LLMCallKnot(_config=KnotConfig(id="llm-call"))
            tool = ToolInvocation(
                tool=_StubTool,
                call=ToolCall(tool_name="search", arguments={"q": "hi"}, call_id="c1"),
                _config=KnotConfig(id="tool-call"),
            )
            Aggregator(
                combine=lambda **results: dict(results),
                _config=KnotConfig(id="agg"),
                llm=llm,
                tool=tool,
            )

        with caplog.at_level(logging.INFO, logger="test.ws4a.event_bus"):
            result = await t.run(RunRequest())

        assert result.succeeded
        agent_records = [r for r in caplog.records if getattr(r, "pirn_extra", None)]
        kinds = {r.pirn_extra["kind"] for r in agent_records}
        assert kinds == {"llm", "tool"}

        llm_record = next(r for r in agent_records if r.pirn_extra["kind"] == "llm")
        assert llm_record.pirn_run_id == result.run_id
        assert llm_record.pirn_knot_id == "llm-call"
        assert llm_record.pirn_extra["model"] == "test-model"

        tool_record = next(r for r in agent_records if r.pirn_extra["kind"] == "tool")
        assert tool_record.pirn_knot_id == "tool-call"
        assert tool_record.pirn_extra["tool_name"] == "search"
