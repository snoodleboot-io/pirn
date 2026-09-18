"""``_SessionFinalizer`` — the terminal knot that surfaces the final session context.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.llm_agent.agent_loop_v2.session_context import SessionContext


class _SessionFinalizer(Knot):
    """Terminal knot — surfaces the final SessionContext as the run output."""

    async def process(self, state: SessionContext, **_: Any) -> SessionContext:
        return state
