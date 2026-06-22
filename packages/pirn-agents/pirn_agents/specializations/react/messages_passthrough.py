"""``MessagesPassthrough`` — identity knot exposing a tuple of messages.

Used by composed agent loops as a seed knot so a ``Knot`` reference
exists for downstream wiring even when the upstream value is a plain
constant.

Algorithm:
    1. Receive the resolved ``messages`` collection at process time.
    2. Convert the collection to an immutable tuple.
    3. Return the tuple unchanged.


References:
    - pirn-native identity pattern; no external algorithm reference.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.agent_message import AgentMessage


class MessagesPassthrough(Knot):
    """Identity knot that re-exposes a tuple of :class:`AgentMessage`."""

    def __init__(
        self,
        *,
        messages: Knot | tuple[AgentMessage, ...] | list[AgentMessage],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: tuple[AgentMessage, ...] | list[AgentMessage],
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        """Convert the input messages collection to a tuple and return it unchanged.

        Args:
            messages: The list or tuple of AgentMessage instances to pass through.

        Returns:
            The same messages as an immutable tuple.
        """
        return tuple(messages)
