"""Unit tests for stateful tool support (S2)."""

from __future__ import annotations

import unittest

from pirn_agents.stateful_tool import StatefulTool, supports_state
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tool_decorator import tool


class TestFunctionToolStateful(unittest.IsolatedAsyncioTestCase):
    async def test_injected_state_persists_across_calls(self) -> None:
        scratch: dict[str, int] = {"count": 0}

        @tool(state=scratch)
        async def counter(amount: int, state: dict[str, int]) -> int:
            """Accumulate into injected state."""
            state["count"] += amount
            return state["count"]

        assert counter.stateful is True
        assert supports_state(counter) is True
        assert isinstance(counter, StatefulTool)
        assert await counter.invoke({"amount": 5}) == 5
        assert await counter.invoke({"amount": 3}) == 8
        assert scratch["count"] == 8

    def test_state_excluded_from_schema(self) -> None:
        @tool(state={"x": 1})
        async def uses_state(amount: int, state: dict[str, int]) -> int:
            """Uses state."""
            return amount

        props = uses_state.parameters_schema["properties"]
        assert "state" not in props
        assert "amount" in props

    def test_state_property_exposes_object(self) -> None:
        resource = object()

        @tool(state=resource)
        async def holds(x: str, state: object) -> str:
            """Holds a resource."""
            return x

        assert holds.state is resource

    def test_non_stateful_tool_reports_false(self) -> None:
        @tool
        async def plain(x: str) -> str:
            """Plain."""
            return x

        assert plain.stateful is False
        assert plain.state is None
        assert supports_state(plain) is False


class TestStubToolStateful(unittest.IsolatedAsyncioTestCase):
    def test_stub_state_exposed(self) -> None:
        state = {"seen": 0}
        stub = StubTool(name="s", state=state)
        assert stub.stateful is True
        assert supports_state(stub) is True
        assert stub.state is state

    async def test_stub_handler_mutates_shared_state(self) -> None:
        state = {"seen": 0}

        def handler(arguments: dict[str, object]) -> int:
            state["seen"] += 1
            return state["seen"]

        stub = StubTool(name="s", state=state, handler=handler)
        assert await stub.invoke({}) == 1
        assert await stub.invoke({}) == 2

    def test_non_stateful_stub_reports_false(self) -> None:
        stub = StubTool(name="s")
        assert stub.stateful is False
        assert stub.state is None


if __name__ == "__main__":
    unittest.main()
