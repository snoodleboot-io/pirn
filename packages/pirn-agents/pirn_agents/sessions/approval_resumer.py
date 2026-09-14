# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``ApprovalResumer`` — resume a suspended run by replaying its prefix.

ADR "agents speaks core" WS3 part 2. Starts a **new** engine run chained to
the suspended one (``_parent_run_id=token.run_id``), replaying every knot the
original run already executed from ``RunHistory``/``DataStore`` — including
the :class:`~pirn_agents.sessions.suspending_approval_check.SuspendingApprovalCheck`
knot itself, which replays right back to its recorded ``Skipped`` outcome —
and letting whatever comes after it in the graph run for the first time
(``ReplaySession(allow_new_knots=True)``). The operator's
:class:`~pirn_agents.sessions.human_decision.HumanDecision` reaches the run as
a bound ``Parameter``, so a HITL gate is a ``Parameter``-bound decision the
downstream graph reads, not a mutation of stored state.

Convention: the value pending approval must reach ``response_knot_id`` through
a ``Parameter`` named ``"response"`` — a ``Parameter`` always executes, even
under replay (its value comes from ``RunRequest.parameters``, not a parent),
so it must be re-supplied on the resumed run's request or binding fails. This
resumer does that automatically, reading the value back from ``data_store``
by the content hash the original recording named, so it is not a second
source of truth.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.run_history import RunHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry

from pirn_agents.sessions.human_decision import HumanDecision
from pirn_agents.sessions.human_decision_identity_resolver import HumanDecisionIdentityResolver
from pirn_agents.sessions.resume_token import ResumeToken


class ApprovalResumer(Knot):
    """Resume a suspended run, injecting the operator's decision as a Parameter."""

    #: Default RunRequest.parameters key the decision is bound under; the graph's
    #: downstream-of-the-gate knots must declare a matching Parameter.
    _default_decision_parameter: ClassVar[str] = "human_decision"

    def __init__(
        self,
        *,
        graph_tapestry: Knot | Tapestry,
        history: Knot | RunHistory,
        data_store: Knot | DataStore,
        token: Knot | ResumeToken,
        decision: Knot | HumanDecision,
        response_knot_id: Knot | str,
        decision_parameter_name: Knot | str = _default_decision_parameter,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            graph_tapestry=graph_tapestry,
            history=history,
            data_store=data_store,
            token=token,
            decision=decision,
            response_knot_id=response_knot_id,
            decision_parameter_name=decision_parameter_name,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        graph_tapestry: Any,
        history: RunHistory,
        data_store: DataStore,
        token: ResumeToken,
        decision: HumanDecision,
        response_knot_id: str,
        decision_parameter_name: str = _default_decision_parameter,
        **_: Any,
    ) -> Any:
        """Resume ``token``'s run past its suspend point with ``decision`` bound.

        Args:
            graph_tapestry: The ``Tapestry`` holding the resumed graph
                (same knot ids/configs as the suspended run, plus whatever is
                genuinely new past the gate). Typed ``Any`` — like
                ``history``/``data_store`` before core's WS3 fix, ``Tapestry``
                itself is not yet a schemable process() parameter type.
            history: The ``RunHistory`` the suspended run was recorded to.
            data_store: The ``DataStore`` the suspended run's outputs were
                content-addressed into.
            token: The resumable handle from the suspend.
            decision: The operator's decision, bound as a ``Parameter`` named
                ``decision_parameter_name`` for the resumed run.
            response_knot_id: The id of the
                ``SuspendingApprovalCheck`` knot the run suspended at, used to
                verify ``token`` against the recording.
            decision_parameter_name: The parameter name the resumed graph's
                post-gate knots read the decision from.

        Returns:
            The resumed ``RunResult``: the prefix up to and including
            ``response_knot_id`` served from the recording, everything after
            it executed for the first time.

        Raises:
            TypeError: If ``history``/``data_store``/``token``/``decision``
                are the wrong type.
            ValueError: If the token's run has already been resumed (a
                continuation exists), or the recorded pending value no longer
                matches ``token.output_hash``.
            KeyError: If ``token.run_id`` is not in ``history``, or
                ``response_knot_id`` has no recorded row in it.
        """
        if not isinstance(history, RunHistory):
            raise TypeError(
                f"ApprovalResumer: history must be a RunHistory, got {type(history).__name__}"
            )
        if not isinstance(data_store, DataStore):
            raise TypeError(
                f"ApprovalResumer: data_store must be a DataStore, got {type(data_store).__name__}"
            )
        if not isinstance(token, ResumeToken):
            raise TypeError(
                f"ApprovalResumer: token must be a ResumeToken, got {type(token).__name__}"
            )
        if not isinstance(decision, HumanDecision):
            raise TypeError(
                f"ApprovalResumer: decision must be a HumanDecision, got {type(decision).__name__}"
            )

        existing_continuations = await history.children_of(token.run_id)
        if any(child.parent_knot_id is None for child in existing_continuations):
            raise ValueError(
                f"ApprovalResumer: run {token.run_id!r} has already been resumed "
                "(a continuation already exists) — the token is single-use"
            )

        # pyright note: this package's pyright config resolves pirn-core via
        # the shared workspace .venv, whose pirn-core is editable-installed
        # from the main checkout — a sibling package, not this branch's copy
        # of pirn-core, so pyright cannot see allow_new_knots there yet even
        # though this worktree's pirn-core defines it (verified: pytest here
        # links against THIS worktree's pirn-core via PYTHONPATH and passes —
        # see test_replay_extends_with_new_knots.py in pirn-core and
        # test_approval_resume_flow.py here). No local override of the shared
        # venv is safe: other worktree sessions share it.
        session = await ReplaySession.from_history(
            history=history,
            run_id=token.run_id,
            allow_new_knots=True,  # pyright: ignore[reportCallIssue]
        )
        pending_row = session.row_for(response_knot_id)
        if pending_row is None:
            raise KeyError(
                f"ApprovalResumer: knot {response_knot_id!r} has no recorded row in run "
                f"{token.run_id!r}"
            )
        recorded_hash = pending_row.parent_input_hashes.get("response", "")
        if recorded_hash != token.output_hash:
            raise ValueError(
                f"ApprovalResumer: stale resume token — the recorded pending value "
                f"({recorded_hash!r}) no longer matches the token ({token.output_hash!r})"
            )
        # A Parameter always executes, even under replay (its value comes
        # from RunRequest.parameters, not a parent) — see ReplaySession's
        # class docstring. The pending response is almost always fed in
        # through one, so it must be re-supplied here under the same name,
        # or the resumed run fails to bind it. Fetched from data_store by the
        # hash the recording itself named, so this is not a second source of
        # truth for the value.
        pending_response = await data_store.get(recorded_hash)

        resume_tapestry = Tapestry(
            store=graph_tapestry.store,
            history=history,
            data_store=data_store,
            identity_resolver=HumanDecisionIdentityResolver(decision),
        )
        request = RunRequest(
            parameters={decision_parameter_name: decision, "response": pending_response}
        )
        return await resume_tapestry.run(
            request,
            replay=session,
            _parent_run_id=token.run_id,
            _parent_knot_id=None,
        )
