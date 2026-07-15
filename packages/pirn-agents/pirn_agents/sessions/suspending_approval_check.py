"""``SuspendingApprovalCheck`` — pause for approval by persisting a resumable run.

Where :class:`~pirn_agents.specializations.human_in_the_loop.approval_check.ApprovalCheck`
gates *within* a single run (returning a bool), this knot lets a run pause and be
resumed *later*: on a non-auto-approved response it checkpoints the current
:class:`RunState` (with the pending response recorded) to a :class:`SessionStore`
and returns a :class:`SuspendSignal` carrying a :class:`ResumeToken`. It composes
with, and never modifies, the in-run approval knots.

Algorithm:
    1. Validate the pending ``response``, ``store``, and ``state``.
    2. If ``auto_approve`` is True, return ``None`` — the in-run fast path
       approves without suspending (parity with ``ApprovalCheck``).
    3. Otherwise record the pending response into the state, content-address and
       persist it, and return a :class:`SuspendSignal` with a resumable token.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.sessions.resume_token import ResumeToken
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_message import SessionMessage
from pirn_agents.sessions.session_store import SessionStore
from pirn_agents.sessions.suspend_signal import SuspendSignal
from pirn_agents.types.agent_response import AgentResponse


class SuspendingApprovalCheck(Knot):
    """Suspend a run at an approval gate, persisting a resumable checkpoint."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        store: Knot | SessionStore,
        state: Knot | RunState,
        auto_approve: Knot | bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            response=response,
            store=store,
            state=state,
            auto_approve=auto_approve,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        store: SessionStore,
        state: RunState,
        auto_approve: bool = False,
        **_: Any,
    ) -> SuspendSignal | None:
        """Suspend and persist the run, or approve in-run when ``auto_approve``.

        Args:
            response: The agent response pending approval.
            store: The session store the paused run is persisted to.
            state: The run state to checkpoint on suspend.
            auto_approve: When True, approve immediately and return ``None``.

        Returns:
            ``None`` when auto-approved (proceed in-run); otherwise a
            :class:`SuspendSignal` whose token resumes the persisted run.

        Raises:
            TypeError: If ``response`` is not an AgentResponse, ``store`` is not a
                SessionStore, or ``state`` is not a RunState.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                f"SuspendingApprovalCheck: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        if not isinstance(store, SessionStore):
            raise TypeError(
                f"SuspendingApprovalCheck: store must be a SessionStore, got {type(store).__name__}"
            )
        if not isinstance(state, RunState):
            raise TypeError(
                f"SuspendingApprovalCheck: state must be a RunState, got {type(state).__name__}"
            )
        if auto_approve:
            return None
        pending = state.with_message(
            SessionMessage(role="approval_request", content=response.content)
        )
        checkpoint = RunCheckpoint.create(pending)
        await store.save(pending.session_id, checkpoint)
        token = ResumeToken(session_id=pending.session_id, checkpoint_id=checkpoint.checkpoint_id)
        return SuspendSignal(token=token)
