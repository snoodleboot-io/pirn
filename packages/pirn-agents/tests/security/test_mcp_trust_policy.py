"""Tests for the S4 MCP trust policy (PIR-265 / PIR-314, PIR-317, PIR-319).

Covers allow-listed servers/tools, unlisted servers/tools rejected by default,
per-tool permission scopes, and sensitive tools routed through the F14 approval
hook. Tools are :class:`StubTool` doubles carrying
:class:`ToolPermissions`; the approval hook is a small in-process double.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from pirn_agents.approval_hook import ApprovalHook
from pirn_agents.security.mcp_trust_error import McpTrustError
from pirn_agents.security.mcp_trust_policy import McpTrustPolicy
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tool_permissions import ToolPermissions


class _DenyingHook(ApprovalHook):
    """Approval hook that records requests and always vetoes."""

    def __init__(self) -> None:
        self.requests: list[str] = []

    async def request_approval(self, *, tool_name: str, arguments: Mapping[str, Any]) -> bool:
        self.requests.append(tool_name)
        return False


def test_allow_listed_server_and_tool_allowed() -> None:
    policy = McpTrustPolicy(allowed_servers={"files": ("read", "list")})
    decision = policy.decide("files", "read")
    assert decision.allowed
    assert not decision.requires_approval


def test_unknown_server_rejected_by_default() -> None:
    policy = McpTrustPolicy(allowed_servers={"files": None})
    decision = policy.decide("shady", "read")
    assert not decision.allowed
    assert "not allow-listed" in decision.reason


def test_unlisted_tool_on_allowed_server_rejected() -> None:
    policy = McpTrustPolicy(allowed_servers={"files": ("read",)})
    assert not policy.is_tool_allowed("files", "delete")
    assert not policy.decide("files", "delete").allowed


def test_none_allow_lists_every_tool_on_server() -> None:
    policy = McpTrustPolicy(allowed_servers={"files": None})
    assert policy.decide("files", "anything").allowed


def test_missing_scope_denies() -> None:
    policy = McpTrustPolicy(allowed_servers={"db": None}, granted_scopes=("db:read",))
    perms = ToolPermissions(scope="db:write", mutating=True)
    decision = policy.decide("db", "update", permissions=perms)
    assert not decision.allowed
    assert "scope" in decision.reason


def test_granted_scope_allows() -> None:
    policy = McpTrustPolicy(allowed_servers={"db": None}, granted_scopes=("db:write",))
    perms = ToolPermissions(scope="db:write", mutating=True)
    assert policy.decide("db", "update", permissions=perms).allowed


def test_sensitive_tool_flags_requires_approval() -> None:
    policy = McpTrustPolicy(allowed_servers={"ops": None})
    perms = ToolPermissions(approval_required=True, mutating=True)
    decision = policy.decide("ops", "deploy", permissions=perms)
    assert decision.allowed
    assert decision.requires_approval


def test_enforce_raises_on_unlisted_server() -> None:
    policy = McpTrustPolicy(allowed_servers={"files": None})
    with pytest.raises(McpTrustError):
        policy.enforce("shady", "read")


async def test_authorize_routes_sensitive_tool_through_hook() -> None:
    # Arrange — a sensitive allow-listed tool + a vetoing approval hook.
    hook = _DenyingHook()
    policy = McpTrustPolicy(allowed_servers={"ops": None}, approval_hook=hook)
    tool = StubTool(name="deploy", permissions=ToolPermissions(approval_required=True))

    # Act
    approved = await policy.authorize(tool, {"env": "prod"}, server="ops")

    # Assert
    assert approved is False
    assert hook.requests == ["deploy"]


async def test_authorize_unlisted_tool_raises_before_hook() -> None:
    hook = _DenyingHook()
    policy = McpTrustPolicy(allowed_servers={"files": ("read",)}, approval_hook=hook)
    tool = StubTool(name="delete", permissions=ToolPermissions(approval_required=True))
    with pytest.raises(McpTrustError):
        await policy.authorize(tool, {}, server="files")
    assert hook.requests == []


async def test_authorize_non_sensitive_tool_skips_hook() -> None:
    hook = _DenyingHook()
    policy = McpTrustPolicy(allowed_servers={"files": None}, approval_hook=hook)
    tool = StubTool(name="read")  # default permissions: no approval
    approved = await policy.authorize(tool, {}, server="files")
    assert approved is True
    assert hook.requests == []


def test_bad_allowed_servers_type_rejected() -> None:
    with pytest.raises(TypeError):
        McpTrustPolicy(allowed_servers=["files"])  # type: ignore[arg-type]
