"""``McpTrustDecision`` — the outcome of evaluating an MCP call against policy.

A frozen record of whether a ``server`` / ``tool`` call is ``allowed`` under the
:class:`~pirn_agents.security.mcp_trust_policy.McpTrustPolicy`, whether it further
``requires_approval`` (a sensitive tool routed through the F14 HITL hook), and a
human-readable ``reason`` for audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class McpTrustDecision(PirnOpaqueValue):
    """Immutable result of an MCP trust-policy evaluation.

    Attributes
    ----------
    allowed:
        ``True`` when the call passes the allow-list and scope checks.
    server:
        The MCP server name evaluated.
    tool:
        The tool name evaluated.
    requires_approval:
        ``True`` when an allowed call still needs human approval before running.
    reason:
        Human-readable explanation of the decision.
    """

    allowed: bool
    server: str
    tool: str
    requires_approval: bool
    reason: str

    def __post_init__(self) -> None:
        """Validate the field types.

        Raises
        ------
        TypeError
            If any field has the wrong type.
        """
        if not isinstance(self.allowed, bool):
            raise TypeError("McpTrustDecision: allowed must be a bool")
        if not isinstance(self.requires_approval, bool):
            raise TypeError("McpTrustDecision: requires_approval must be a bool")
        for label in ("server", "tool", "reason"):
            if not isinstance(getattr(self, label), str):
                raise TypeError(f"McpTrustDecision: {label} must be a str")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return a stable content-addressing view of the decision."""
        return {
            "allowed": self.allowed,
            "server": self.server,
            "tool": self.tool,
            "requires_approval": self.requires_approval,
            "reason": self.reason,
        }
