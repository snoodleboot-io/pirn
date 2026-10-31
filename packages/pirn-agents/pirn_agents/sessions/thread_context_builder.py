"""``ThreadContextBuilder`` — reconstruct a resumed thread's turns as F17 context.

Maps each :class:`ConversationTurn` of a resumed :class:`ConversationThread` onto
an F17 :class:`~pirn_agents.context.context_item.ContextItem`, preserving turn
order via each item's ``position``. The resulting items feed the F17
:class:`~pirn_agents.context.context_assembler.ContextAssembler` unchanged, so a
durable thread is reconstructed into a token-budgeted context without this module
re-implementing any context assembly.

Algorithm:
    1. Validate the resolved ``thread``.
    2. Emit one :class:`ContextItem` per turn, ``position`` = turn index,
       ``kind`` = ``"message"``, content = ``"{role}: {content}"``.
    3. Wrap them in a :class:`~pirn_agents.sessions.thread_context.ThreadContext`
       (PIR-874) carrying the thread's session id and the item count.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.context.context_item import ContextItem
from pirn_agents.sessions.conversation_thread import ConversationThread
from pirn_agents.sessions.thread_context import ThreadContext


class ThreadContextBuilder(Knot):
    """Turn a durable :class:`ConversationThread` into ordered F17 context items."""

    def __init__(
        self,
        *,
        thread: Knot | ConversationThread,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(thread=thread, _config=_config, **kwargs)

    async def process(
        self,
        thread: ConversationThread,
        **_: Any,
    ) -> ThreadContext:
        """Reconstruct ``thread``'s prior turns as ordered context items.

        Args:
            thread: The resumed durable conversation thread.

        Returns:
            A :class:`ThreadContext` whose ``data`` is one :class:`ContextItem`
            per turn, in turn order (feed ``.data`` to the F17
            :class:`ContextAssembler`) and whose frame names the thread.
        """
        items = tuple(
            ContextItem(
                content=f"{turn.role}: {turn.content}",
                kind="message",
                position=turn.index,
            )
            for turn in thread.turns
        )
        return ThreadContext(items, session_id=thread.session_id)
