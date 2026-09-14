"""Durable sessions & HITL resume (F14, rebased onto core in ADR agents-speaks-core WS3).

A session is one engine run per turn linked by ``_parent_run_id``
(:class:`~pirn_agents.sessions.session_chain.SessionChain`); ``RunState`` is a
read-model :meth:`~pirn_agents.sessions.run_state.RunState.from_chain` projects
from that chain, not a persisted checkpoint blob. HITL suspend is a core
``Skipped(reason="awaiting_human")``; resume
(:class:`~pirn_agents.sessions.approval_resumer.ApprovalResumer`) replays the
suspended run's recorded prefix via ``ReplaySession(allow_new_knots=True)``.
Multi-turn thread persistence is
:class:`~pirn_agents.sessions.conversation_thread.ConversationThread` over
core's own ``DataStore``/``RunHistory`` — no separate session store.
"""

__all__: list[str] = []
