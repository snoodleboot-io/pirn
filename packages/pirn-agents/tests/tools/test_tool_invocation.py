"""Unit tests for :class:`ToolInvocation` (PIR-733).

The point of the class is that a tool call becomes a graph node, so most of
these assert on what the *engine* saw — lineage rows, scheduling — rather than
only on the returned value.
"""

from __future__ import annotations

import asyncio
import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry

from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation import ToolInvocation
from pirn_agents.tools.tool_status import ToolStatus


class _Echo(Tool):
    """Returns its arguments; records how often it was invoked."""

    def __init__(self, name: str = "echo") -> None:
        self._name = name
        self.calls: list[Mapping[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "echo the arguments"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object"}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        self.calls.append(dict(arguments))
        return dict(arguments)


class _Slow(_Echo):
    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        await asyncio.sleep(0.05)
        return await super().invoke(arguments)


class _RaisingDsn(_Echo):
    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        raise RuntimeError("failed: postgres://user:s3cr3tp4ssw0rd@host/db")


def _call(call_id: str = "c1", tool_name: str = "echo", **arguments: Any) -> ToolCall:
    return ToolCall(tool_name=tool_name, arguments=arguments, call_id=call_id)


class TestToolInvocationIsAGraphNode(unittest.IsolatedAsyncioTestCase):
    async def test_a_tool_call_now_produces_a_lineage_row(self) -> None:
        """The whole point: before this, a tool call left no engine trace."""
        tool = _Echo()
        with Tapestry() as t:
            ToolInvocation(tool=tool, call=_call(a=1), _config=KnotConfig(id="inv"))

        result = await t.run(RunRequest())

        assert result.succeeded
        row = next(r for r in result.lineage if r.knot_id == "inv")
        assert row.outcome == "ok"
        assert row.output_hash is not None
        assert result.outputs["inv"].result == {"a": 1}

    async def test_the_tool_is_visible_in_lineage_as_a_config_value(self) -> None:
        """Two invocations of *different* tools must be distinguishable (PIR-836)."""
        with Tapestry() as one:
            ToolInvocation(tool=_Echo("alpha"), call=_call(a=1), _config=KnotConfig(id="inv"))
        with Tapestry() as two:
            ToolInvocation(tool=_Echo("beta"), call=_call(a=1), _config=KnotConfig(id="inv"))

        row_one = next(r for r in (await one.run(RunRequest())).lineage if r.knot_id == "inv")
        row_two = next(r for r in (await two.run(RunRequest())).lineage if r.knot_id == "inv")

        assert row_one.config_values_hash is not None
        assert row_one.config_values_hash != row_two.config_values_hash

    async def test_call_may_arrive_from_an_upstream_knot(self) -> None:
        tool = _Echo()

        @knot
        async def plan() -> ToolCall:
            return _call("from-upstream", a=2)

        with Tapestry() as t:
            upstream = plan(_config=KnotConfig(id="plan"))
            ToolInvocation(tool=tool, call=upstream, _config=KnotConfig(id="inv"))

        result = await t.run(RunRequest())

        assert result.outputs["inv"].call_id == "from-upstream"
        assert tool.calls == [{"a": 2}]


class TestToolInvocationFanOut(unittest.IsolatedAsyncioTestCase):
    async def test_the_engine_schedules_sibling_calls_concurrently(self) -> None:
        """N invocations under one Aggregator run as one wave, not in series.

        This is the payoff PIR-733 names: the engine already runs a ready wave
        concurrently, so fan-out no longer needs a hand-rolled ``asyncio.gather``
        outside it.
        """
        with Tapestry() as t:
            calls = {
                f"inv{i}": ToolInvocation(
                    tool=_Slow(f"slow-{i}"),
                    call=_call(f"c{i}", a=i),
                    _config=KnotConfig(id=f"inv{i}"),
                )
                for i in range(4)
            }
            Aggregator(
                combine=lambda **results: dict(results),
                _config=KnotConfig(id="agg"),
                **calls,
            )

        started = asyncio.get_running_loop().time()
        result = await t.run(RunRequest())
        elapsed = asyncio.get_running_loop().time() - started

        assert result.succeeded
        assert len(result.outputs["agg"]) == 4
        # 4 x 50ms serially is 200ms; concurrently it is ~50ms. The bound is
        # loose so a loaded machine does not fail it (see PIR-810/PIR-777).
        assert elapsed < 0.15, f"fan-out took {elapsed:.3f}s — did it run in series?"

    async def test_one_failing_call_does_not_fail_its_siblings(self) -> None:
        with Tapestry() as t:
            ok = ToolInvocation(tool=_Echo(), call=_call("c1", a=1), _config=KnotConfig(id="ok"))
            bad = ToolInvocation(
                tool=_RaisingDsn(), call=_call("c2", a=2), _config=KnotConfig(id="bad")
            )
            Aggregator(
                combine=lambda **results: dict(results),
                _config=KnotConfig(id="agg"),
                ok=ok,
                bad=bad,
            )

        result = await t.run(RunRequest())

        assert result.succeeded
        assert result.outputs["ok"].status is ToolStatus.OK
        assert result.outputs["bad"].status is ToolStatus.ERROR


class TestToolInvocationErrorHandling(unittest.IsolatedAsyncioTestCase):
    async def test_a_raising_tool_becomes_an_error_result_not_a_failed_run(self) -> None:
        with Tapestry() as t:
            ToolInvocation(tool=_RaisingDsn(), call=_call(), _config=KnotConfig(id="inv"))

        result = await t.run(RunRequest())

        assert result.succeeded
        outcome = result.outputs["inv"]
        assert outcome.status is ToolStatus.ERROR
        assert outcome.result is None
        assert outcome.latency is not None

    async def test_dsn_credentials_are_scrubbed_from_message_and_traceback(self) -> None:
        """The batch path used to leak these into lineage; scrub at the boundary.

        ``ExceptionRecord`` does not scrub, and it carries the message twice —
        in ``message`` and again inside ``traceback_text`` — so scrubbing only
        the former would still persist the credential to history.
        """
        with Tapestry() as t:
            ToolInvocation(tool=_RaisingDsn(), call=_call(), _config=KnotConfig(id="inv"))

        outcome = (await t.run(RunRequest())).outputs["inv"]

        assert outcome.error is not None
        assert "s3cr3tp4ssw0rd" not in outcome.error
        assert "<redacted>" in outcome.error
        assert outcome.exception is not None
        assert "s3cr3tp4ssw0rd" not in outcome.exception.message
        assert "s3cr3tp4ssw0rd" not in outcome.exception.traceback_text

    async def test_rejects_a_non_tool(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a Tool"):
            with Tapestry():
                ToolInvocation(
                    tool="not a tool",  # type: ignore[arg-type]
                    call=_call(),
                    _config=KnotConfig(id="inv"),
                )

    async def test_rejects_a_non_toolcall(self) -> None:
        """Core validates a literal config value at construction, not at run time."""
        with self.assertRaisesRegex(TypeError, "config value failed validation"):
            with Tapestry():
                ToolInvocation(
                    tool=_Echo(),
                    call="not a call",  # type: ignore[arg-type]
                    _config=KnotConfig(id="inv"),
                )
