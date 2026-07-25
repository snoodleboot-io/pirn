"""``ApprovalResumer`` — resume a suspended run by injecting a human decision.

Algorithm:
    1. Load the checkpoint the :class:`ResumeToken` points at.
    2. Reject a missing session (nothing suspended) or a stale token (its
       ``checkpoint_id`` no longer matches the stored state — already resumed or
       superseded). The stale-token check makes the token single-use, so a
       decision is never injected twice (no duplicate side effects).
    3. Record the :class:`HumanDecision` into the run state, persist the resumed
       state (advancing the checkpoint id), and return it for the run to continue.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.sessions.human_decision import HumanDecision
from pirn_agents.sessions.resume_token import ResumeToken
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_message import SessionMessage
from pirn_agents.sessions.session_store import SessionStore


class ApprovalResumer(Knot):
    """Resume a suspended run, injecting the operator's :class:`HumanDecision`."""

    def __init__(
        self,
        *,
        store: Knot | SessionStore,
        token: Knot | ResumeToken,
        decision: Knot | HumanDecision,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(store=store, token=token, decision=decision, _config=_config, **kwargs)

    async def process(
        self,
        store: SessionStore,
        token: ResumeToken,
        decision: HumanDecision,
        **_: Any,
    ) -> RunState:
        """Inject ``decision`` into the suspended run and return the resumed state.

        Args:
            store: The session store holding the suspended run.
            token: The resumable token yielded at suspend time.
            decision: The operator's approval decision to inject.

        Returns:
            The resumed :class:`RunState` with the decision recorded.

        Raises:
            TypeError: If any argument is of the wrong type.
            ValueError: If no run is suspended for the token, or the token is
                stale (already resumed / superseded).
        """
        if not isinstance(store, SessionStore):
            raise TypeError(
                f"ApprovalResumer: store must be a SessionStore, got {type(store).__name__}"
            )
        if not isinstance(token, ResumeToken):
            raise TypeError(
                f"ApprovalResumer: token must be a ResumeToken, got {type(token).__name__}"
            )
        if not isinstance(decision, HumanDecision):
            raise TypeError(
                f"ApprovalResumer: decision must be a HumanDecision, got {type(decision).__name__}"
            )
        checkpoint = await store.load(token.session_id)
        if checkpoint is None:
            raise ValueError(f"ApprovalResumer: no suspended run for session {token.session_id!r}")
        if checkpoint.checkpoint_id != token.checkpoint_id:
            raise ValueError(
                f"ApprovalResumer: stale resume token for session {token.session_id!r} "
                "(already resumed or superseded)"
            )
        verdict = "approved" if decision.approved else "rejected"
        resumed = checkpoint.state.with_message(
            SessionMessage(role="approval_decision", content=f"{verdict}: {decision.note or ''}")
        )
        await store.save(resumed.session_id, RunCheckpoint.create(resumed))
        return resumed
