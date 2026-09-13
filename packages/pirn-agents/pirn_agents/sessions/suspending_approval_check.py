"""``SuspendingApprovalCheck`` — pause a run for approval as an engine-native skip.

ADR "agents speaks core" WS3 part 2 (updated for the WS0 core seam merged to
main after part 2: `Knot.__call__` now passes a `Skipped` returned directly
from `process()` through bare — no sentinel-exception/`__call__`-interception
dance needed; a "denied approval" is explicitly named in `Knot.__call__`'s own
docstring as the motivating case).

Where
:class:`~pirn_agents.specializations.human_in_the_loop.approval_check.ApprovalCheck`
gates *within* a single run (returning a bool), this knot lets the run pause
*as a run*: on a non-auto-approved response it produces
``Skipped(reason="awaiting_human")`` — the engine's own "this knot did not
run" outcome, propagating to every downstream knot the normal way, with no
separate checkpoint write. The turn's ``RunResult`` (already durably recorded
by ``RunHistory``/``DataStore`` — the engine does that unconditionally) *is*
the suspended state; nothing here persists anything of its own.

A caller that needs a resumable handle for the suspended run reads it back
from the ``RunResult`` afterwards — see
:meth:`~pirn_agents.sessions.suspend_signal.SuspendSignal.from_run_result`.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.skipped import Skipped

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
    ) -> Any:
        """Pass ``response`` through when auto-approved, else declare a suspend.

        Args:
            response: The agent response pending approval.
            auto_approve: When True, approve immediately and pass through.

        Returns:
            ``response`` unchanged when auto-approved, else
            ``Skipped(reason="awaiting_human")`` — passed through bare by
            ``Knot.__call__``, so the engine records this knot (and every
            downstream knot depending on it) as skipped.
        """
        if auto_approve:
            return response
        return Skipped(reason="awaiting_human")
