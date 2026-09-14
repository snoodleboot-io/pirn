"""``ApprovalHook`` — the human-approval seam for gated tool calls (F11/F14).

:class:`ApprovalHook` is the point where an application decides whether a tool
call flagged ``approval_required`` may proceed. The base class is a deliberate,
intentional **no-op that auto-approves**: handed no hook (or the base hook), a
gated tool runs exactly as an ungated one would. Subclasses override
:meth:`request_approval` to prompt a human, consult a policy engine, or block —
those overrides are what the security (F11) and human-in-the-loop (F14)
surfaces will supply.

The module-level :func:`authorize_tool_call` coroutine — and
:meth:`ApprovalHook.authorize`, its implementation — is the policy this
package's own approval seam evaluates: it consults the capability's
permission metadata and only routes through the hook when approval is
actually required, so unrestricted tools pay nothing.  Since PIR-865 the
seam is wired as the graph form the ADR "agents speaks core" (WS1) always
intended:
:class:`~pirn_agents.agent.tool_approval_check.ToolApprovalCheck` (a core
``Check``) evaluates this same policy as a knot, and
:meth:`~pirn_agents.tools.tool_factory.ToolFactory.for_call` wires it behind
a core ``Gate`` in front of every call whose tool requires approval — so a
denied call's own outcome is a core ``Skipped``, the tool's ``process()`` is
never invoked, and the model is told the call was skipped rather than that
it failed (see :meth:`pirn_agents.tools.tool_result.ToolResult.from_result`,
``gated=True``).  A call an application refuses for an unrelated reason —
naming an unregistered tool, or arguments the declaration refuses — still
recorded as the call's own ``Err`` through
:class:`~pirn_agents.tools.tool_call_rejection.ToolCallRejection`, which this
does not change: that is a rejection, not an approval decision.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.tools.tool_factory import ToolFactory


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

    @staticmethod
    async def authorize(
        tool: Any,
        arguments: Mapping[str, Any],
        hook: ApprovalHook | None = None,
    ) -> bool:
        """Return whether a call to ``tool`` with ``arguments`` may proceed.

        Capabilities whose permissions do not require approval are allowed
        immediately without invoking ``hook``. Those that require approval
        are routed through ``hook`` (or an auto-approving default when
        ``hook`` is ``None``).
        """
        factory = ToolFactory.of(tool)
        if not factory.requires_approval():
            return True
        resolved = hook if hook is not None else ApprovalHook()
        return await resolved.request_approval(tool_name=factory.name, arguments=arguments)


async def authorize_tool_call(
    tool: Any,
    arguments: Mapping[str, Any],
    hook: ApprovalHook | None = None,
) -> bool:
    """Return whether a call to ``tool`` with ``arguments`` may proceed.

    Thin wrapper kept for the pinned public import path (see
    ``tests/test_ws5_s1_import_surface.py``); see :meth:`ApprovalHook.authorize`.
    """
    return await ApprovalHook.authorize(tool, arguments, hook)
