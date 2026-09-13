"""``SuspendingApprovalCheck`` — pause a run for approval as an engine-native skip.

ADR "agents speaks core" WS3 part 2. Where
:class:`~pirn_agents.specializations.human_in_the_loop.approval_check.ApprovalCheck`
gates *within* a single run (returning a bool), this knot lets the run pause
*as a run*: on a non-auto-approved response it produces
``Skipped(reason="awaiting_human")`` — the engine's own "this knot did not
run" outcome, propagating to every downstream knot the normal way, with no
separate checkpoint write. The turn's ``RunResult`` (already durably recorded
by ``RunHistory``/``DataStore`` — the engine does that unconditionally) *is*
the suspended state; nothing here persists anything of its own.

Algorithm:
    1. If ``auto_approve`` is True, pass ``response`` through unchanged (the
       in-run fast path, parity with ``ApprovalCheck``).
    2. Otherwise ``process()`` raises :class:`_AwaitingHumanError`, which
       ``__call__`` intercepts and converts to
       ``Skipped(reason="awaiting_human")`` — the same conversion
       :class:`pirn.nodes.gate.gate.Gate` performs for ``_GateClosedError``.

A caller that needs a resumable handle for the suspended run reads it back
from the ``RunResult`` afterwards — see
:meth:`~pirn_agents.sessions.suspend_signal.SuspendSignal.from_run_result`.
"""

from __future__ import annotations

from typing import Any

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.skipped import Skipped

from pirn_agents.sessions._awaiting_human_error import _AwaitingHumanError
from pirn_agents.types.messaging.agent_response import AgentResponse


class SuspendingApprovalCheck(Knot):
    """Suspend a run at an approval gate as ``Skipped(reason="awaiting_human")``."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        auto_approve: Knot | bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            response=response,
            auto_approve=auto_approve,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        auto_approve: bool = False,
        **_: Any,
    ) -> AgentResponse:
        """Pass ``response`` through when auto-approved, else signal a suspend.

        Args:
            response: The agent response pending approval.
            auto_approve: When True, approve immediately and pass through.

        Returns:
            ``response`` unchanged, when auto-approved.

        Raises:
            _AwaitingHumanError: When not auto-approved; converted to
                ``Skipped(reason="awaiting_human")`` by :meth:`__call__`.
        """
        if auto_approve:
            return response
        raise _AwaitingHumanError

    async def __call__(self, parent_results: Any) -> Any:
        result = await super().__call__(parent_results)
        if isinstance(result, Err) and result.record.exc_type == "_AwaitingHumanError":
            return Skipped(reason="awaiting_human")
        return result
