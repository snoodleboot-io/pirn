"""``McpTrustPolicy`` — allow-list + scope + approval gate for MCP tool calls.

The policy is the single guard an agent runs before dispatching a call to a tool
sourced from an MCP server. It composes three checks, cheapest first:

1. **Allow-list.** Only explicitly allow-listed servers are trusted; unknown
   servers are rejected by default. Each server maps to the set of tool names it
   may expose (``None`` allow-lists *every* tool on that server).
2. **Permission scope.** The tool's
   :class:`~pirn_agents.tool_permissions.ToolPermissions` ``scope`` (F26 metadata)
   must be one the caller has been granted.
3. **Human approval.** Allowed calls whose permissions set ``approval_required``
   are routed through the F14
   :func:`~pirn_agents.approval_hook.authorize_tool_call` seam so a human (or a
   policy engine) can veto them.

:meth:`decide` is the pure, synchronous evaluation (allow-list + scope);
:meth:`authorize` adds the async approval step and returns whether the call may
finally proceed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.approval_hook import ApprovalHook, authorize_tool_call
from pirn_agents.permissioned_tool import permissions_of
from pirn_agents.security.mcp_trust_decision import McpTrustDecision
from pirn_agents.security.mcp_trust_error import McpTrustError
from pirn_agents.tool import Tool
from pirn_agents.tool_permissions import ToolPermissions


class McpTrustPolicy:
    """Gate MCP tool calls on server allow-list, permission scope, and approval."""

    def __init__(
        self,
        *,
        allowed_servers: Mapping[str, Sequence[str] | None],
        granted_scopes: Sequence[str] = (),
        approval_hook: ApprovalHook | None = None,
    ) -> None:
        """Configure the allow-list, granted scopes, and approval hook.

        Args:
            allowed_servers: Map of trusted server name to the tuple of tool
                names it may expose; a ``None`` value allow-lists every tool on
                that server.
            granted_scopes: The permission scopes the caller holds.
            approval_hook: Optional F14 approval hook for sensitive tools; the
                auto-approving default is used when ``None``.

        Raises:
            TypeError: If ``allowed_servers`` is not a mapping, a value is not a
                sequence of strings or ``None``, or ``approval_hook`` is set but
                not an :class:`ApprovalHook`.
        """
        if not isinstance(allowed_servers, Mapping):
            raise TypeError("McpTrustPolicy: allowed_servers must be a Mapping")
        if approval_hook is not None and not isinstance(approval_hook, ApprovalHook):
            raise TypeError("McpTrustPolicy: approval_hook must be an ApprovalHook or None")
        allow: dict[str, frozenset[str] | None] = {}
        for server, tools in allowed_servers.items():
            if not isinstance(server, str) or not server:
                raise TypeError("McpTrustPolicy: server names must be non-empty strings")
            if tools is None:
                allow[server] = None
                continue
            if isinstance(tools, str) or not isinstance(tools, Sequence):
                raise TypeError(
                    f"McpTrustPolicy: allowed tools for {server!r} must be a sequence or None"
                )
            allow[server] = frozenset(str(name) for name in tools)
        self._allowed = allow
        self._granted_scopes = frozenset(str(scope) for scope in granted_scopes)
        self._approval_hook = approval_hook

    def is_server_allowed(self, server: str) -> bool:
        """Return whether ``server`` is allow-listed."""
        return server in self._allowed

    def is_tool_allowed(self, server: str, tool: str) -> bool:
        """Return whether ``tool`` on ``server`` is allow-listed."""
        if server not in self._allowed:
            return False
        permitted = self._allowed[server]
        return permitted is None or tool in permitted

    def decide(
        self,
        server: str,
        tool: str,
        *,
        permissions: ToolPermissions | None = None,
    ) -> McpTrustDecision:
        """Evaluate allow-list + scope for a ``server``/``tool`` call.

        Args:
            server: The MCP server name.
            tool: The tool name.
            permissions: The tool's permission metadata; the inert default is
                used when ``None``.

        Returns:
            An :class:`McpTrustDecision` (approval is *not* consulted here).

        Raises:
            TypeError: If ``server`` / ``tool`` are not strings.
        """
        if not isinstance(server, str) or not isinstance(tool, str):
            raise TypeError("McpTrustPolicy: server and tool must be strings")
        perms = permissions if permissions is not None else ToolPermissions()
        if not self.is_server_allowed(server):
            return self._deny(server, tool, f"MCP server {server!r} is not allow-listed")
        if not self.is_tool_allowed(server, tool):
            return self._deny(server, tool, f"tool {tool!r} is not allow-listed on {server!r}")
        if perms.scope is not None and perms.scope not in self._granted_scopes:
            return self._deny(
                server, tool, f"missing required scope {perms.scope!r} for tool {tool!r}"
            )
        return McpTrustDecision(
            allowed=True,
            server=server,
            tool=tool,
            requires_approval=perms.approval_required,
            reason="allow-listed and in scope",
        )

    def enforce(
        self,
        server: str,
        tool: str,
        *,
        permissions: ToolPermissions | None = None,
    ) -> McpTrustDecision:
        """Return the decision, raising :class:`McpTrustError` when disallowed."""
        decision = self.decide(server, tool, permissions=permissions)
        if not decision.allowed:
            raise McpTrustError(decision.reason, server=server, tool=tool)
        return decision

    async def authorize(
        self,
        tool: Tool,
        arguments: Mapping[str, Any],
        *,
        server: str,
    ) -> bool:
        """Fully authorize an MCP tool call: allow-list, scope, then approval.

        Args:
            tool: The tool to be invoked (its ``permissions`` are read via F26's
                :func:`~pirn_agents.permissioned_tool.permissions_of`).
            arguments: The arguments the tool would run with.
            server: The MCP server the tool came from.

        Returns:
            ``True`` when the call is allow-listed, in scope, and approved.

        Raises:
            McpTrustError: If the allow-list or scope check fails.
        """
        perms = permissions_of(tool)
        self.enforce(server, tool.name, permissions=perms)
        return await authorize_tool_call(tool, arguments, self._approval_hook)

    def _deny(self, server: str, tool: str, reason: str) -> McpTrustDecision:
        """Build a denied :class:`McpTrustDecision`."""
        return McpTrustDecision(
            allowed=False,
            server=server,
            tool=tool,
            requires_approval=False,
            reason=reason,
        )
