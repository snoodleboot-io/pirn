"""``SessionChain`` — a session is a chain of engine runs, not a stored blob.

ADR "agents speaks core" WS3 part 2. A session is one turn's ``Tapestry.run()``
per interaction (or per resume), linked to the turn before it via
``_parent_run_id`` — the same field the engine already sets when a
``SubTapestry`` knot spawns a nested run, distinguished here by
``parent_knot_id=None`` (no knot spawned this run; the session runner started
it directly). The session id travels in ``RunRequest.parameters`` so any turn's
knots can read "which session am I in", and :meth:`turns_of` walks
``RunHistory.children_of`` from the session's root run to recover the whole
chain — no new ``RunHistory`` query is needed, and no snapshot is ever
persisted as the source of truth. :class:`~pirn_agents.sessions.run_state.RunState`
is the read-model projected from the chain (:meth:`RunState.from_chain`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from pirn.backends.base.run_history import RunHistory
    from pirn.core.run_request import RunRequest
    from pirn.core.run_result import RunResult
    from pirn.tapestry import Tapestry


class SessionChain:
    """Run and enumerate a session's turns as a ``parent_run_id`` chain."""

    #: The parameter name a turn's ``RunRequest`` carries the session id under.
    session_id_parameter: ClassVar[str] = "session_id"

    @staticmethod
    async def run_turn(
        tapestry: Tapestry,
        request: RunRequest,
        *,
        session_id: str,
        previous_run_id: str | None = None,
        **run_kwargs: Any,
    ) -> RunResult:
        """Run one session turn, chained to ``previous_run_id`` if given.

        Args:
            tapestry: The tapestry to run the turn's graph against.
            request: The turn's ``RunRequest``. A copy carrying ``session_id``
                under :attr:`SessionChain.session_id_parameter` is what actually runs — the
                caller's ``request.parameters`` are preserved alongside it.
            session_id: The session this turn belongs to. Non-empty.
            previous_run_id: The prior turn's ``run_id``, or ``None`` for the
                session's first turn (the root run).
            **run_kwargs: Forwarded to ``Tapestry.run`` (e.g. ``terminals``,
                ``replay``).

        Returns:
            The turn's ``RunResult``.

        Raises:
            ValueError: If ``session_id`` is empty.
            TypeError: If ``previous_run_id`` is given but not a str.
        """
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("SessionChain.run_turn: session_id must be a non-empty str")
        if previous_run_id is not None and not isinstance(previous_run_id, str):
            raise TypeError(
                f"SessionChain.run_turn: previous_run_id must be a str or None, "
                f"got {type(previous_run_id).__name__}"
            )
        stamped = request.model_copy(
            update={
                "parameters": {**request.parameters, SessionChain.session_id_parameter: session_id}
            }
        )
        return await tapestry.run(
            stamped,
            _parent_run_id=previous_run_id,
            _parent_knot_id=None,
            **run_kwargs,
        )

    @staticmethod
    async def turns_of(history: RunHistory, root_run_id: str) -> list[RunResult]:
        """Return every turn of the session rooted at ``root_run_id``, in order.

        Walks ``RunHistory.children_of`` from the root, at each step choosing
        the (earliest-started) child whose ``parent_knot_id`` is ``None`` —
        the session-chain successor — and ignoring any child spawned by a
        ``SubTapestry`` knot inside that turn's own graph (which also sets
        ``parent_run_id`` but *does* set ``parent_knot_id``). Stops when a run
        has no such child.

        Args:
            history: The ``RunHistory`` the chain's runs were recorded to.
            root_run_id: The session's first turn's ``run_id``.

        Returns:
            The chain's ``RunResult``s, oldest first, starting with the root.

        Raises:
            KeyError: If ``root_run_id`` is not present in ``history``.
        """
        root = await history.get_run(root_run_id)
        if root is None:
            raise KeyError(f"SessionChain.turns_of: run {root_run_id!r} not found in history")
        chain: list[RunResult] = [root]
        current = root
        while True:
            children = await history.children_of(current.run_id)
            successors = sorted(
                (child for child in children if child.parent_knot_id is None),
                key=lambda run: run.started_at,
            )
            if not successors:
                break
            current = successors[0]
            chain.append(current)
        return chain
