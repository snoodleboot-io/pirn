"""``CheckpointForker`` — branch a run chain at a recorded point for what-if runs.

ADR "agents speaks core" WS3 part 3. A fork is a branch of the session chain:
given the ``(run_id, output_hash)`` of the knot being forked from — the same
shape :class:`~pirn_agents.sessions.resume_token.ResumeToken` uses for HITL
resume — starts a **new** run chained to the source (``_parent_run_id``) that
replays the source's recorded prefix
(``ReplaySession(allow_new_knots=True)``, verified against the fork point)
and executes whatever diverges — new knot ids, or the same ones fed different
``Parameter`` values via the caller's ``RunRequest`` — for the first time.
Two forks taken from the same source share that prefix and diverge
independently; nothing is persisted beyond what the engine already records
for the new run.
"""

from __future__ import annotations

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.run_history import RunHistory
from pirn.core.run_request import RunRequest
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry

from pirn_agents.determinism.fork_result import ForkResult
from pirn_agents.sessions.resume_token import ResumeToken


class CheckpointForker:
    """Branch a new run from a recorded point in an existing run chain."""

    async def fork(
        self,
        *,
        tapestry: Tapestry,
        history: RunHistory,
        data_store: DataStore,
        fork_point: ResumeToken,
        source_knot_id: str,
        request: RunRequest | None = None,
    ) -> ForkResult:
        """Fork the run chain at ``fork_point``, running ``tapestry``'s graph.

        Args:
            tapestry: The tapestry holding the graph to run — the shared
                prefix up to (and including) ``source_knot_id`` plus whatever
                diverges after it.
            history: The ``RunHistory`` the source run was recorded to, and
                the forked run is recorded to.
            data_store: The ``DataStore`` the source run's outputs were
                content-addressed into.
            fork_point: The ``(run_id, output_hash)`` identifying the exact
                recorded invocation to fork from.
            source_knot_id: The id of the knot ``fork_point.output_hash``
                names, used to verify the fork point against the recording.
            request: The forked run's ``RunRequest`` — supply any ``Parameter``
                values the diverging part of the graph needs (a ``Parameter``
                always executes, even under replay, so any value the shared
                prefix bound must be re-supplied here too). Defaults to an
                empty request.

        Returns:
            The :class:`ForkResult` naming the fork's provenance and carrying
            the new run's ``RunResult``.

        Raises:
            TypeError: If ``history``, ``data_store``, or ``fork_point`` is
                the wrong type.
            KeyError: If ``fork_point.run_id`` is not in ``history``, or
                ``source_knot_id`` has no recorded row in it.
            ValueError: If the recorded output hash for ``source_knot_id`` no
                longer matches ``fork_point.output_hash``.
        """
        if not isinstance(history, RunHistory):
            raise TypeError(
                f"CheckpointForker.fork: history must be a RunHistory, got {type(history).__name__}"
            )
        if not isinstance(data_store, DataStore):
            raise TypeError(
                f"CheckpointForker.fork: data_store must be a DataStore, "
                f"got {type(data_store).__name__}"
            )
        if not isinstance(fork_point, ResumeToken):
            raise TypeError(
                f"CheckpointForker.fork: fork_point must be a ResumeToken, "
                f"got {type(fork_point).__name__}"
            )
        # pyright note: see the identical note in
        # pirn_agents.sessions.approval_resumer — this package's pyright
        # config resolves pirn-core via the shared workspace .venv's
        # editable install of the main checkout, not this worktree/branch's
        # copy, so it cannot see allow_new_knots yet even though it is real
        # (proven by pytest here, which links this worktree's pirn-core via
        # PYTHONPATH).
        session = await ReplaySession.from_history(
            history=history,
            run_id=fork_point.run_id,
            allow_new_knots=True,  # pyright: ignore[reportCallIssue]
        )
        row = session.row_for(source_knot_id)
        if row is None:
            raise KeyError(
                f"CheckpointForker.fork: knot {source_knot_id!r} has no recorded row in run "
                f"{fork_point.run_id!r}"
            )
        if row.output_hash != fork_point.output_hash:
            raise ValueError(
                f"CheckpointForker.fork: stale fork point — the recorded output "
                f"({row.output_hash!r}) no longer matches ({fork_point.output_hash!r})"
            )
        effective_request = request if request is not None else RunRequest()
        result = await tapestry.run(
            effective_request,
            replay=session,
            _parent_run_id=fork_point.run_id,
            _parent_knot_id=None,
        )
        return ForkResult(
            new_run_id=result.run_id,
            source_run_id=fork_point.run_id,
            forked_from_output_hash=fork_point.output_hash,
            result=result,
        )
