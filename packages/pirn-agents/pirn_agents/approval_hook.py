"""``ApprovalHook`` — the human-approval seam for gated tool calls (F11/F14).

:class:`ApprovalHook` is the point where an application decides whether a tool
call flagged ``approval_required`` may proceed. The base class is a deliberate,
intentional **no-op that auto-approves**: handed no hook (or the base hook), a
gated tool runs exactly as an ungated one would. Subclasses override
:meth:`request_approval` to prompt a human, consult a policy engine, or block —
those overrides are what the security (F11) and human-in-the-loop (F14)
surfaces will supply.

The module-level :func:`authorize_tool_call` coroutine is the guard callers run
before executing a tool: it consults the tool's permission metadata and only
routes through the hook when approval is actually required, so unrestricted
tools pay nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.permissioned_tool import requires_approval
from pirn_agents.tool import Tool


class ApprovalHook:
    """No-op approval seam fired before a gated tool call.

    Override :meth:`request_approval` to gate execution. The base method
    approves unconditionally by design; the unmodified class is the zero-cost
    default used when no human-in-the-loop policy is wired.
    """

    async def request_approval(self, *, tool_name: str, arguments: Mapping[str, Any]) -> bool:
        """Return whether the flagged call to ``tool_name`` may proceed.

        Args:
            tool_name: Name of the tool whose call is being gated.
            arguments: The arguments the tool would be invoked with.

        Returns:
            ``True`` to allow the call. The base implementation is a
            deliberate auto-approve.
        """
        return True


async def authorize_tool_call(
    tool: Tool,
    arguments: Mapping[str, Any],
    hook: ApprovalHook | None = None,
) -> bool:
    """Return whether a call to ``tool`` with ``arguments`` may proceed.

    Tools whose permissions do not require approval are allowed immediately
    without invoking ``hook``. Tools that require approval are routed through
    ``hook`` (or an auto-approving default when ``hook`` is ``None``).
    """
    if not requires_approval(tool):
        return True
    resolved = hook if hook is not None else ApprovalHook()
    return await resolved.request_approval(tool_name=tool.name, arguments=arguments)
