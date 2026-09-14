"""``ToolFactory.for_call``/``run_call`` approval gating (PIR-865).

A tool whose permissions require approval gets a
:class:`~pirn_agents.agent.tool_approval_check.ToolApprovalCheck` behind a
core ``Gate`` wired in front of it; a denial closes the gate, so the tool's
own ``process()`` is never called and the call's outcome is a core
``Skipped`` rather than an ``Err``. Covers both call shapes ``for_call``
builds a knot for: an ordinary ``Tool`` subclass (named inputs) and a
schema-declared, packed-arguments capability (``StubTool``, MCP tools, the
deprecated ``invoke``-shaped shim).
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.emitters.emitter import Emitter
from pirn.managers.status_event import StatusEvent
from pirn.tapestry import Tapestry

from pirn_agents.agent.approval_hook import ApprovalHook
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_permissions import ToolPermissions


class _CapturingEmitter(Emitter):
    def __init__(self) -> None:
        self.statuses: list[StatusEvent] = []

    async def on_status(self, event: StatusEvent) -> None:
        self.statuses.append(event)

    def tool_events(self) -> list[StatusEvent]:
        return [e for e in self.statuses if e.extra.get("kind") == "tool"]


class _AllowHook(ApprovalHook):
    async def request_approval(self, *, tool_name: str, arguments: Any) -> bool:
        return True


class _DenyHook(ApprovalHook):
    async def request_approval(self, *, tool_name: str, arguments: Any) -> bool:
        return False


class Adder(Tool):
    """An ordinary, gated tool: named inputs, no packing."""

    tool_name: ClassVar[str] = "adder"
    permissions: ClassVar[ToolPermissions] = ToolPermissions(approval_required=True)
    calls: ClassVar[list[dict[str, Any]]] = []

    def __init__(
        self, *, left: Knot | int, right: Knot | int = 0, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(left=left, right=right, _config=_config, **kwargs)

    async def process(self, left: int, right: int = 0, **_: Any) -> int:
        Adder.calls.append({"left": left, "right": right})
        return left + right


def _call(call_id: str, **arguments: Any) -> ToolCall:
    return ToolCall(tool_name="adder", arguments=arguments, call_id=call_id)


class TestForCallOrdinaryShape(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        Adder.calls.clear()

    async def test_unrestricted_tool_is_not_gated_at_all(self) -> None:
        """No approval required: the knot's only parents are its own arguments."""
        factory = StubTool(name="plain")
        with Tapestry():
            knot = factory.for_call(ToolCall(tool_name="plain", arguments={}, call_id="p1"))
        assert not any("approval" in name for name in knot.parents)

    async def test_approved_call_runs_normally(self) -> None:
        factory = Adder.factory()
        with Tapestry() as t:
            factory.for_call(_call("c1", left=2, right=3), approval_hook=_AllowHook(), tapestry=t)
        result = await t.run(RunRequest())
        assert result.outputs["c1"] == 5
        assert Adder.calls == [{"left": 2, "right": 3}]

    async def test_denied_call_is_skipped_and_never_runs(self) -> None:
        factory = Adder.factory()
        with Tapestry() as t:
            factory.for_call(_call("c2", left=2, right=3), approval_hook=_DenyHook(), tapestry=t)
        result = await t.run(RunRequest())
        assert "c2" in result.skipped
        assert "c2" not in result.outputs
        assert Adder.calls == []

    async def test_denied_call_reports_no_tool_event_for_its_own_identity(self) -> None:
        """A closed gate means process() -- and Tool.__call__'s own recorder -- never runs.

        Distinct from a *container* (``ToolInvocation``) that reports the
        rendered view regardless of outcome: this is the tool's own,
        per-identity ``AgentCallRecorder`` event, which only fires from
        inside ``Tool.__call__`` -- i.e. only when ``process()`` actually ran.
        """
        emitter = _CapturingEmitter()
        factory = Adder.factory()
        with Tapestry(emitters=[emitter]) as t:
            factory.for_call(_call("c3", left=1, right=1), approval_hook=_DenyHook(), tapestry=t)
        await t.run(RunRequest())
        assert emitter.tool_events() == []

    async def test_without_a_hook_the_auto_approving_default_runs_the_call(self) -> None:
        factory = Adder.factory()
        with Tapestry() as t:
            factory.for_call(_call("c4", left=10, right=5), tapestry=t)
        result = await t.run(RunRequest())
        assert result.outputs["c4"] == 15

    async def test_denied_calls_own_lineage_row_is_never_dispatched(self) -> None:
        factory = Adder.factory()
        with Tapestry() as t:
            factory.for_call(_call("c5", left=1, right=1), approval_hook=_DenyHook(), tapestry=t)
        result = await t.run(RunRequest())
        row = next(r for r in result.lineage if r.knot_id == "c5")
        assert row.outcome == "skipped"


class TestForCallPackedShape(unittest.IsolatedAsyncioTestCase):
    """``StubTool`` (and MCP tools, and the deprecated invoke shim) pack all
    arguments into one declared ``arguments`` input -- the approval gate must
    not corrupt that payload."""

    async def test_approved_call_receives_the_unmodified_arguments(self) -> None:
        stub = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        result = await stub.run_call(
            ToolCall(tool_name="danger", arguments={"input": "x"}, call_id="s1"),
            approval_hook=_AllowHook(),
        )
        assert isinstance(result, Ok)
        assert result.value == "stub-result"
        assert stub.invocations == [{"input": "x"}]

    async def test_denied_call_is_skipped_and_never_invoked(self) -> None:
        stub = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        result = await stub.run_call(
            ToolCall(tool_name="danger", arguments={"input": "x"}, call_id="s2"),
            approval_hook=_DenyHook(),
        )
        assert isinstance(result, Skipped)
        assert stub.invocations == []

    async def test_bound_and_default_values_still_reach_the_approved_call(self) -> None:
        base = StubTool(
            name="danger",
            permissions=ToolPermissions(approval_required=True),
            handler=lambda args: args,
        )
        stub = base.bind(extra="bound-value")
        result = await stub.run_call(
            ToolCall(tool_name="danger", arguments={"input": "x"}, call_id="s3"),
            approval_hook=_AllowHook(),
        )
        assert isinstance(result, Ok)
        assert result.value == {"input": "x", "extra": "bound-value"}


class TestRunCall(unittest.IsolatedAsyncioTestCase):
    """``run_call`` bypasses the ambient engine, but a genuine parent (the
    approval gate) must still be resolved rather than silently ignored."""

    def setUp(self) -> None:
        Adder.calls.clear()

    async def test_unrestricted_tool_still_uses_the_fast_bare_call_path(self) -> None:
        factory = StubTool(name="plain", result=42)
        result = await factory.run_call(
            ToolCall(tool_name="plain", arguments={"input": "x"}, call_id="p1")
        )
        assert isinstance(result, Ok)
        assert result.value == 42

    async def test_approved_call_runs_through_a_real_engine_pass(self) -> None:
        factory = Adder.factory()
        result = await factory.run_call(_call("c1", left=4, right=1), approval_hook=_AllowHook())
        assert isinstance(result, Ok)
        assert result.value == 5

    async def test_denied_call_is_skipped_not_silently_run(self) -> None:
        """The bug this closes: a bare ``knot({})`` call never resolves parents."""
        factory = Adder.factory()
        result = await factory.run_call(_call("c2", left=4, right=1), approval_hook=_DenyHook())
        assert isinstance(result, Skipped)
        assert Adder.calls == []

    async def test_a_raising_gated_call_still_surfaces_as_err(self) -> None:
        class Boom(Tool):
            tool_name: ClassVar[str] = "boom"
            permissions: ClassVar[ToolPermissions] = ToolPermissions(approval_required=True)

            def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
                super().__init__(_config=_config, **kwargs)

            async def process(self, **_: Any) -> Any:
                raise RuntimeError("kaboom")

        result = await Boom.factory().run_call(
            ToolCall(tool_name="boom", arguments={}, call_id="b1"), approval_hook=_AllowHook()
        )
        assert isinstance(result, Err)
        assert "kaboom" in result.record.message


if __name__ == "__main__":
    unittest.main()
