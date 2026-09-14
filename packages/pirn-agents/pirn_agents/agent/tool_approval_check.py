"""``ToolApprovalCheck`` — the ``Check`` half of the tool-call approval seam.

Wire one in front of a tool knot with ``Gate(input=<the call's arguments
knot>, check=ToolApprovalCheck(...))`` (ADR agents-speaks-core; see
:mod:`pirn_agents.agent.approval_hook`) so a denied call closes the gate
instead of an execution ever being attempted: the engine's default
``SKIP_IF_PARENT_FAILED`` error policy skips a knot whose parent is
``Skipped`` without ever calling its ``process()``, so the tool never runs.
The call's own outcome is then a core ``Skipped`` — the model is told the
call was skipped, not that it failed — see :attr:`skip_reason` and
:meth:`pirn_agents.tools.tool_result.ToolResult.from_result` (``gated=True``).
:meth:`~pirn_agents.tools.tool_factory.ToolFactory.for_call` is what actually
wires this Check behind a ``Gate`` for every capability whose
:class:`~pirn_agents.tools.tool_permissions.ToolPermissions` require
approval; a capability that does not is never gated at all.

Named ``ToolApprovalCheck`` rather than the shorter ``ApprovalCheck`` because
:class:`pirn_agents.specializations.human_in_the_loop.approval_check.ApprovalCheck`
already holds that name for a different, unrelated seam — pausing a whole
:class:`~pirn_agents.types.messaging.agent_response.AgentResponse` for a human
decision, not gating one tool call — and class names must stay unique across
the workspace (``docs/contributing/knot-remediation-process.md``).

``process()`` evaluates the same policy
:meth:`pirn_agents.agent.approval_hook.ApprovalHook.authorize` already
implements — a capability whose permissions do not require approval is
approved without consulting a hook; one that does is routed through the
:class:`~pirn_agents.agent.approval_hook.ApprovalHook` (or its auto-approving
default when none is wired).

Algorithm:
    1. Resolve ``tool`` into a :class:`~pirn_agents.tools.tool_factory.ToolFactory`.
    2. If its permissions do not require approval, return ``True`` — the
       gate stays open without ever consulting ``hook``.
    3. Otherwise await ``hook.request_approval(tool_name=..., arguments=...)``
       (or the base, auto-approving :class:`ApprovalHook` when ``hook`` is
       ``None``) and return its verdict.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.check import Check

from pirn_agents.agent.approval_hook import ApprovalHook
from pirn_agents.tools.tool_factory import ToolFactory


class ToolApprovalCheck(Check):
    """Whether a gated tool call may proceed — the ``check=`` half of an approval ``Gate``.

    A tool whose permissions do not set ``approval_required`` never needs one
    of these wired at all; :meth:`ToolFactory.for_call` only builds one when
    the capability requires it.
    """

    #: The semantic reason a denied approval names.  Core's ``Gate`` always
    #: records ``"gate_closed"`` in its own lineage row (it has no per-check
    #: custom skip-reason seam) and the downstream tool knot's own row is the
    #: engine's generic ``"parent_failed_or_skipped"`` propagation reason —
    #: neither names *why* in a way worth showing a model.  This package's
    #: own rendering uses this constant instead wherever it knows a call was
    #: gated (:meth:`pirn_agents.tools.tool_result.ToolResult.from_result`,
    #: ``gated=True``), so the model reads "approval denied" rather than
    #: either engine-internal string.
    skip_reason: ClassVar[str] = "approval_denied"

    def __init__(
        self,
        *,
        tool: Knot | ToolFactory | Any,
        arguments: Knot | Mapping[str, Any],
        hook: Any = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        """Wire the capability, its call arguments, and the approval hook.

        Args:
            tool: The capability the call would invoke — any spelling
                :meth:`ToolFactory.of` accepts.
            arguments: The call's resolved arguments, passed to the hook
                verbatim (never mutated or validated here).
            hook: The :class:`~pirn_agents.agent.approval_hook.ApprovalHook`
                to consult, or ``None`` for the auto-approving default.
                Typed ``Any``: a bare, non-pydantic class core's eager
                per-input ``TypeAdapter`` build cannot schema (the same
                reason ``ParallelToolExecutor(hook=...)`` is ``Any``).
            _config: Framework metadata; ``id`` is required as for any knot.
        """
        super().__init__(tool=tool, arguments=arguments, hook=hook, _config=_config, **kwargs)

    async def process(
        self,
        tool: Any,
        arguments: Mapping[str, Any],
        hook: Any = None,
        **_: Any,
    ) -> bool:
        """Return whether the call may proceed.

        Args:
            tool: The resolved capability.
            arguments: The call's resolved arguments.
            hook: The resolved :class:`~pirn_agents.agent.approval_hook.ApprovalHook`,
                or ``None`` for the auto-approving default.

        Returns:
            ``True`` when the capability's permissions do not require
            approval, or when the hook approves the call; ``False`` otherwise.
        """
        return await ApprovalHook.authorize(tool, arguments, hook)
