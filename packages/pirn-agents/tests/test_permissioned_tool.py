"""Unit tests for permission metadata exposure and detection (S3)."""

from __future__ import annotations

import unittest

from pirn_agents.permissioned_tool import PermissionedTool, permissions_of, requires_approval
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tool_decorator import tool
from pirn_agents.tool_permissions import ToolPermissions


class TestPermissionMetadataOnTool(unittest.TestCase):
    def test_decorator_attaches_metadata(self) -> None:
        @tool(scope="db:read", mutating=False, cost_hint=0.5)
        async def reader(x: str) -> str:
            """Read-only tool."""
            return x

        assert reader.permissions.scope == "db:read"
        assert reader.permissions.mutating is False
        assert reader.permissions.cost_hint == 0.5

    def test_mutating_classification(self) -> None:
        @tool(mutating=True)
        async def writer(x: str) -> str:
            """Mutating tool."""
            return x

        assert writer.permissions.mutating is True

    def test_metadata_in_describe_schema(self) -> None:
        @tool(scope="s", approval_required=True)
        async def gated(x: str) -> str:
            """Gated tool."""
            return x

        assert gated.describe()["permissions"] == {"scope": "s", "approval_required": True}


class TestPermissionedToolProtocol(unittest.TestCase):
    def test_function_tool_satisfies_protocol(self) -> None:
        @tool(scope="s")
        async def scoped() -> str:
            """Scoped."""
            return ""

        assert isinstance(scoped, PermissionedTool)

    def test_stub_tool_satisfies_protocol(self) -> None:
        stub = StubTool(name="s", permissions=ToolPermissions(mutating=True))
        assert isinstance(stub, PermissionedTool)

    def test_permissions_of_falls_back_to_default(self) -> None:
        class Bare:
            pass

        assert permissions_of(Bare()).is_default is True

    def test_permissions_of_reads_tool(self) -> None:
        stub = StubTool(name="s", permissions=ToolPermissions(scope="x"))
        assert permissions_of(stub).scope == "x"


class TestRequiresApproval(unittest.TestCase):
    def test_true_when_flagged(self) -> None:
        @tool(approval_required=True)
        async def gated() -> str:
            """Gated."""
            return ""

        assert requires_approval(gated) is True

    def test_false_by_default(self) -> None:
        @tool
        async def plain() -> str:
            """Plain."""
            return ""

        assert requires_approval(plain) is False

    def test_false_for_non_permissioned_object(self) -> None:
        assert requires_approval(object()) is False


if __name__ == "__main__":
    unittest.main()
