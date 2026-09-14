# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``RunResumer`` — rehydrate a session's current read model from its run chain.

ADR "agents speaks core" WS3 part 2. A session's first turn is run with its
``run_id`` set to the session id (``RunRequest(run_id=session_id)`` via
:meth:`~pirn_agents.sessions.session_chain.SessionChain.run_turn`), so the
session id doubles as the chain's root ``run_id``. Resuming is then a pure
read: walk the chain from that root
(:meth:`~pirn_agents.sessions.session_chain.SessionChain.turns_of`) and
project the current :class:`~pirn_agents.sessions.run_state.RunState` from it
— no store, no write, so repeated calls are idempotent and side-effect-free,
same as before this rewrite.
"""

from __future__ import annotations

from typing import Any

from pirn.backends.base.run_history import RunHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_chain import SessionChain


class RunResumer(Knot):
    """Rehydrate a session's current :class:`RunState` from its run chain."""

    def __init__(
        self,
        *,
        history: Knot | RunHistory,
        session_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(history=history, session_id=session_id, _config=_config, **kwargs)

    async def process(
        self,
        history: RunHistory,
        session_id: str,
        **_: Any,
    ) -> RunState | None:
        """Return the projected run state for ``session_id``, or ``None``.

        Args:
            history: The ``RunHistory`` the session's turns were recorded to.
            session_id: The session to rehydrate — the ``run_id`` its first
                turn was run with.

        Returns:
            The rehydrated :class:`RunState`, or ``None`` when no run exists
            for ``session_id``.

        Raises:
            TypeError: If ``history`` is not a ``RunHistory`` or
                ``session_id`` is not a non-empty str.
        """
        if not isinstance(history, RunHistory):
            raise TypeError(
                f"RunResumer: history must be a RunHistory, got {type(history).__name__}"
            )
        if not isinstance(session_id, str) or not session_id:
            raise TypeError("RunResumer: session_id must be a non-empty str")
        try:
            turns = await SessionChain.turns_of(history, session_id)
        except KeyError:
            return None
        return RunState.from_chain(session_id=session_id, turns=turns)
