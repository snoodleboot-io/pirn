"""``_SessionFinalizer`` — the terminal knot that surfaces the final session context.

Part of the ``examples.llm_agent.agent_loop`` example.
"""

from __future__ import annotations

from pirn.core.knot import Knot

from examples.llm_agent.agent_loop.session_context import SessionContext


class _SessionFinalizer(Knot):
    """Terminal knot — surfaces the final session context as the run output."""

    async def process(self, state: SessionContext, **_) -> SessionContext:
        return state
