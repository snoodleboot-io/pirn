"""Unit tests for :class:`ToolInvocation` — a tool call is a knot (ADR WS1).

Most of these assert on what the *engine* saw — lineage rows keyed by the
call id, scheduling, the call knot's own ``Err`` — rather than only on the
returned value.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any, ClassVar

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.emitters.emitter import Emitter
from pirn.managers.knot_state import KnotState
from pirn.managers.status_event import StatusEvent
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.check import Check
from pirn.nodes.gate.gate import Gate
from pirn.tapestry import Tapestry

from pirn_agents.agent.approval_hook import ApprovalHook
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation import ToolInvocation
from pirn_agents.tools.tool_permissions import ToolPermissions
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus


class _CapturingEmitter(Emitter):
    def __init__(self) -> None:
        self.statuses: list[StatusEvent] = []

    async def on_status(self, event: StatusEvent) -> None:
        self.statuses.append(event)

    def tool_events(self) -> list[StatusEvent]:
        return [e for e in self.statuses if e.extra.get("kind") == "tool"]


class Echo(Tool):
    """Return the arguments; a shared list records how often it ran."""

    calls: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, *, a: Knot | int, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(a=a, _config=_config, **kwargs)

    async def process(self, a: int, **_: Any) -> dict[str, Any]:
        Echo.calls.append({"a": a})
        return {"a": a}


class Gated(Echo):
    """``Echo``, but requiring approval (PIR-865)."""

    calls: ClassVar[list[dict[str, Any]]] = []
    permissions: ClassVar[ToolPermissions] = ToolPermissions(approval_required=True)

    async def process(self, a: int, **_: Any) -> dict[str, Any]:
        Gated.calls.append({"a": a})
        return {"a": a}


class _DenyHook(ApprovalHook):
    async def request_approval(self, *, tool_name: str, arguments: Any) -> bool:
        return False


class _AllowHook(ApprovalHook):
    async def request_approval(self, *, tool_name: str, arguments: Any) -> bool:
        return True


class Slow(Echo):
    async def process(self, a: int, **_: Any) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        return await super().process(a=a)


class RaisingDsn(Echo):
    async def process(self, a: int, **_: Any) -> dict[str, Any]:
        raise RuntimeError("failed: postgres://user:s3cr3tp4ssw0rd@host/db")


class Flaky(Echo):
    attempts: ClassVar[int] = 0

    async def process(self, a: int, **_: Any) -> dict[str, Any]:
        Flaky.attempts += 1
        if Flaky.attempts < 3:
            raise RuntimeError("transient")
        return {"a": a}


class Deny(Check):
    def __init__(self, *, call: Knot, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(call=call, _config=_config, **kwargs)

    async def process(self, call: ToolCall, **_: Any) -> bool:
        return False


def _call(call_id: str = "c1", tool_name: str = "echo", **arguments: Any) -> ToolCall:
    return ToolCall(tool_name=tool_name, arguments=arguments, call_id=call_id)


class TestToolCallsEmitThroughAgentCallRecorder(unittest.IsolatedAsyncioTestCase):
    """ADR WS4a: every tool call the engine runs reports through the emitter path.

    ``ToolInvocation`` reports its one call under its own id on the outer run
    and claims the report from the tool knot, so one call is one event; a tool
    knot wired directly (a fan-out) reports itself.  No ``ToolInvocationHook``
    is needed.
    """

    async def test_a_successful_call_emits_a_succeeded_tool_event(self) -> None:
        emitter = _CapturingEmitter()
        with Tapestry(emitters=[emitter]) as t:
            ToolInvocation(tool=Echo, call=_call(a=1), _config=KnotConfig(id="inv"))

        result = await t.run(RunRequest())

        assert result.succeeded, result.exceptions
        events = emitter.tool_events()
        assert len(events) == 1
        event = events[0]
        assert event.knot_id == "inv"
        assert event.run_id == result.run_id
        assert event.state is KnotState.SUCCEEDED
        assert event.extra["tool_name"] == "echo"
        assert event.extra["call_id"] == "c1"
        assert isinstance(event.extra["latency"], float)

    async def test_a_raising_call_emits_a_failed_tool_event_with_scrubbed_detail(self) -> None:
        emitter = _CapturingEmitter()
        with Tapestry(emitters=[emitter]) as t:
            ToolInvocation(tool=RaisingDsn, call=_call(a=1), _config=KnotConfig(id="inv"))

        await t.run(RunRequest())

        events = emitter.tool_events()
        assert len(events) == 1
        assert events[0].state is KnotState.FAILED
        assert events[0].detail is not None
        assert "s3cr3tp4ssw0rd" not in events[0].detail

    async def test_a_refused_call_emits_a_failed_tool_event(self) -> None:
        emitter = _CapturingEmitter()
        with Tapestry(emitters=[emitter]) as t:
            ToolInvocation(tool=Echo, call=_call(a="not an int"), _config=KnotConfig(id="inv"))

        await t.run(RunRequest())

        events = emitter.tool_events()
        assert len(events) == 1
        assert events[0].state is KnotState.FAILED
        assert events[0].extra["call_id"] == "c1"
        assert events[0].knot_id == "inv"
        assert "ToolArgumentValidationError" in (events[0].detail or "")

    async def test_a_tool_knot_wired_directly_reports_itself(self) -> None:
        emitter = _CapturingEmitter()
        with Tapestry(emitters=[emitter]) as t:
            Echo(a=1, _config=KnotConfig(id="c9"))

        result = await t.run(RunRequest())

        assert result.succeeded, result.exceptions
        events = emitter.tool_events()
        assert [(e.knot_id, e.extra["call_id"], e.extra["tool_name"]) for e in events] == [
            ("c9", "c9", "echo")
        ]


class TestATooCallIsAKnot(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        Echo.calls.clear()

    async def test_the_call_knot_runs_under_the_call_id(self) -> None:
        with Tapestry() as t:
            ToolInvocation(tool=Echo, call=_call(a=1), _config=KnotConfig(id="inv"))
        result = await t.run(RunRequest())

        assert result.succeeded
        view = result.outputs["inv"]
        assert isinstance(view, ToolResult)
        assert view.result == {"a": 1}
        assert view.latency is not None
        children = await t.history.children_of(result.run_id)
        rows = {row.knot_id: row for child in children for row in child.lineage}
        assert rows["c1"].outcome == "ok"
        assert rows["c1"].knot_class.endswith("Echo")

    async def test_the_tool_and_its_arguments_are_the_calls_config_values(self) -> None:
        with Tapestry() as one:
            ToolInvocation(tool=Echo, call=_call(a=1), _config=KnotConfig(id="inv"))
        with Tapestry() as two:
            ToolInvocation(tool=Echo, call=_call(a=2), _config=KnotConfig(id="inv"))
        run_one = await one.run(RunRequest())
        run_two = await two.run(RunRequest())
        row_one = next(
            r
            for c in await one.history.children_of(run_one.run_id)
            for r in c.lineage
            if r.knot_id == "c1"
        )
        row_two = next(
            r
            for c in await two.history.children_of(run_two.run_id)
            for r in c.lineage
            if r.knot_id == "c1"
        )
        assert row_one.config_values_hash != row_two.config_values_hash

    async def test_call_may_arrive_from_an_upstream_knot(self) -> None:
        @knot
        async def plan() -> ToolCall:
            return _call("from-upstream", a=2)

        with Tapestry() as t:
            upstream = plan(_config=KnotConfig(id="plan"))
            ToolInvocation(tool=Echo, call=upstream, _config=KnotConfig(id="inv"))
        result = await t.run(RunRequest())

        assert result.outputs["inv"].call_id == "from-upstream"
        assert Echo.calls == [{"a": 2}]

    async def test_the_capability_may_arrive_from_an_upstream_knot(self) -> None:
        with Tapestry() as t:
            capability = Parameter("tool", Any, default=Echo, _config=KnotConfig(id="cap"))
            ToolInvocation(tool=capability, call=_call(a=3), _config=KnotConfig(id="inv"))
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert result.outputs["inv"].result == {"a": 3}


class TestFanOut(unittest.IsolatedAsyncioTestCase):
    async def test_the_engine_schedules_sibling_calls_concurrently(self) -> None:
        with Tapestry() as t:
            calls = {f"c{i}": Slow(a=i, _config=KnotConfig(id=f"c{i}")) for i in range(4)}
            Aggregator(
                combine=lambda **results: dict(results), _config=KnotConfig(id="agg"), **calls
            )

        started = asyncio.get_running_loop().time()
        result = await t.run(RunRequest())
        elapsed = asyncio.get_running_loop().time() - started

        assert result.succeeded
        assert len(result.outputs["agg"]) == 4
        assert elapsed < 0.15, f"fan-out took {elapsed:.3f}s — did it run in series?"

    async def test_one_failing_call_does_not_fail_its_siblings(self) -> None:
        with Tapestry() as t:
            ok = ToolInvocation(tool=Echo, call=_call("c1", a=1), _config=KnotConfig(id="ok"))
            bad = ToolInvocation(
                tool=RaisingDsn, call=_call("c2", a=2), _config=KnotConfig(id="bad")
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


class TestOutcomes(unittest.IsolatedAsyncioTestCase):
    async def test_a_raising_tool_is_the_calls_own_err_reported_as_a_view(self) -> None:
        with Tapestry() as t:
            ToolInvocation(tool=RaisingDsn, call=_call(a=1), _config=KnotConfig(id="inv"))
        result = await t.run(RunRequest())

        assert result.succeeded
        view = result.outputs["inv"]
        assert view.status is ToolStatus.ERROR
        assert view.result is None
        assert view.latency is not None
        children = await t.history.children_of(result.run_id)
        inner = next(c for c in children if c.parent_knot_id == "inv")
        assert [r.exc_type for r in inner.exceptions] == ["RuntimeError"]

    async def test_dsn_credentials_are_scrubbed_from_message_and_traceback(self) -> None:
        with Tapestry() as t:
            ToolInvocation(tool=RaisingDsn, call=_call(a=1), _config=KnotConfig(id="inv"))
        view = (await t.run(RunRequest())).outputs["inv"]

        assert view.error is not None
        assert "s3cr3tp4ssw0rd" not in view.error
        assert "<redacted>" in view.error
        assert view.exception is not None
        assert "s3cr3tp4ssw0rd" not in view.exception.message
        assert "s3cr3tp4ssw0rd" not in view.exception.traceback_text

    async def test_refused_arguments_are_recorded_as_the_calls_err(self) -> None:
        with Tapestry() as t:
            ToolInvocation(tool=Echo, call=_call(nope=1), _config=KnotConfig(id="inv"))
        result = await t.run(RunRequest())

        assert result.succeeded
        view = result.outputs["inv"]
        assert view.status is ToolStatus.ERROR
        assert view.exception is not None
        assert view.exception.exc_type == "ToolArgumentValidationError"
        assert "missing_required" in view.error

    async def test_a_timeout_is_reported_as_timeout(self) -> None:
        with Tapestry() as t:
            ToolInvocation(tool=Slow, call=_call(a=1), timeout=0.01, _config=KnotConfig(id="inv"))
        view = (await t.run(RunRequest())).outputs["inv"]
        assert view.status is ToolStatus.TIMEOUT
        assert view.exception is not None
        assert view.exception.exc_type == "KnotTimeoutError"

    async def test_retry_is_the_engines(self) -> None:
        Flaky.attempts = 0
        with Tapestry() as t:
            ToolInvocation(
                tool=Flaky,
                call=_call(a=1),
                retry=KnotRetryPolicy(max_attempts=3, base_delay=0.0, jitter=False),
                _config=KnotConfig(id="inv"),
            )
        result = await t.run(RunRequest())
        view = result.outputs["inv"]
        assert view.status is ToolStatus.OK
        assert Flaky.attempts == 3
        children = await t.history.children_of(result.run_id)
        row = next(r for c in children for r in c.lineage if r.knot_id == "c1")
        assert row.extra.get("attempts") == 3

    async def test_a_denied_approval_skips_the_call(self) -> None:
        """Approval is a Check feeding a core Gate in front of the call: denied = Skipped."""
        with Tapestry() as t:
            call = Parameter("call", ToolCall, default=_call(a=1), _config=KnotConfig(id="call"))
            gated = Gate(
                input=call,
                check=Deny(call=call, _config=KnotConfig(id="deny")),
                _config=KnotConfig(id="gate"),
            )
            ToolInvocation(tool=Echo, call=gated, _config=KnotConfig(id="inv"))
        result = await t.run(RunRequest())

        assert result.succeeded
        assert "inv" in result.skipped
        assert "inv" not in result.outputs

    async def test_rejects_a_non_toolcall_config_value_at_construction(self) -> None:
        with self.assertRaisesRegex(TypeError, "config value failed validation"):
            with Tapestry():
                ToolInvocation(
                    tool=Echo,
                    call="not a call",  # type: ignore[arg-type]
                    _config=KnotConfig(id="inv"),
                )

    async def test_rejects_a_non_capability_in_process(self) -> None:
        with Tapestry():
            inv = ToolInvocation(tool=Echo, call=_call(), _config=KnotConfig(id="inv"))
        result = await inv({"tool": "not a tool", "call": _call()})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"


class TestApprovalGating(unittest.IsolatedAsyncioTestCase):
    """PIR-865: ``ToolFactory.for_call`` wires the approval Gate; a denial is Skipped."""

    def setUp(self) -> None:
        Gated.calls.clear()

    async def test_approved_call_runs_normally(self) -> None:
        with Tapestry() as t:
            ToolInvocation(
                tool=Gated,
                call=_call(a=1),
                approval_hook=_AllowHook(),
                _config=KnotConfig(id="inv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        view = result.outputs["inv"]
        assert view.status is ToolStatus.OK
        assert view.result == {"a": 1}
        assert Gated.calls == [{"a": 1}]

    async def test_denied_call_is_skipped_not_an_error(self) -> None:
        with Tapestry() as t:
            ToolInvocation(
                tool=Gated,
                call=_call(a=1),
                approval_hook=_DenyHook(),
                _config=KnotConfig(id="inv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        view = result.outputs["inv"]
        assert view.status is ToolStatus.SKIPPED
        assert view.error == "call skipped: approval denied"
        assert Gated.calls == []

    async def test_denied_call_reports_no_tool_event_for_the_tools_own_identity(self) -> None:
        emitter = _CapturingEmitter()
        with Tapestry(emitters=[emitter]) as t:
            ToolInvocation(
                tool=Gated,
                call=_call(a=1),
                approval_hook=_DenyHook(),
                _config=KnotConfig(id="inv"),
            )
        await t.run(RunRequest())
        # ToolInvocation's own container-level event still fires (unchanged,
        # pre-existing behaviour: it reports the rendered view regardless of
        # outcome) -- exactly one event, attributed to "inv", not to Gated's
        # own knot id (which never ran process() at all).
        events = emitter.tool_events()
        assert len(events) == 1
        assert events[0].knot_id == "inv"
        assert events[0].state is KnotState.FAILED
        assert events[0].detail == "call skipped: approval denied"
