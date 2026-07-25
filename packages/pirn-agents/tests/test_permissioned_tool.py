"""Unit tests for the permission capability facet on the :class:`Tool` base (S3)."""

from __future__ import annotations

import unittest

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


class TestPermissionedToolFacet(unittest.TestCase):
    def test_function_tool_exposes_scope(self) -> None:
        @tool(scope="s")
        async def scoped() -> str:
            """Scoped."""
            return ""

        assert scoped.permissions.scope == "s"

    def test_stub_tool_exposes_permissions(self) -> None:
        stub = StubTool(name="s", permissions=ToolPermissions(mutating=True))
        assert stub.permissions.mutating is True

    def test_plain_tool_falls_back_to_default(self) -> None:
        @tool
        async def plain(x: str) -> str:
            """Plain."""
            return x

        assert plain.permissions.is_default is True

    def test_permissions_reads_tool(self) -> None:
        stub = StubTool(name="s", permissions=ToolPermissions(scope="x"))
        assert stub.permissions.scope == "x"


class TestRequiresApproval(unittest.TestCase):
    def test_true_when_flagged(self) -> None:
        @tool(approval_required=True, scope="x")
        async def gated() -> str:
            """Gated."""
            return ""

        assert gated.permissions.scope == "x"
        assert gated.permissions.approval_required is True
        assert gated.requires_approval() is True

    def test_false_by_default(self) -> None:
        @tool
        async def plain() -> str:
            """Plain."""
            return ""

        assert plain.permissions.is_default is True
        assert plain.requires_approval() is False


if __name__ == "__main__":
    unittest.main()
