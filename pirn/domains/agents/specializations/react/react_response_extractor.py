"""``ReActResponseExtractor`` — accumulated messages → :class:`AgentResponse`.

Walks the accumulated transcript backwards from the most recent
assistant message and synthesises an :class:`AgentResponse`. When a
``Final Answer:`` marker is present, the suffix after the marker
becomes the response content and ``finished`` is set to ``True``.
Otherwise the trailing assistant content is surfaced verbatim with
``finished`` set to ``False`` so callers can detect that the loop
exhausted its iteration budget.

Algorithm:
    1. Receive the resolved ``messages`` tuple at process time.
    2. Iterate over messages in reverse order.
    3. Find the first (most recent) message with role ``"assistant"``.
    4. If the message content contains ``"Final Answer:"``, split on the
       marker and return the suffix as the response content with
       ``finish_reason="stop"``.
    5. Otherwise return the full content with ``finish_reason="length"``.
    6. If no assistant message is found, return an empty response with
       ``finish_reason="length"``.


References:
    - Yao et al. (2023) "ReAct: Synergizing Reasoning and Acting in Language Models"
      https://arxiv.org/abs/2210.03629
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.domains.agents.types.agent_response import AgentResponse


class ReActResponseExtractor(Knot):
    """Build an :class:`AgentResponse` from the accumulated messages."""

    _final_answer_marker: str = "Final Answer:"

    def __init__(
        self,
        *,
        messages: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: tuple[AgentMessage, ...] | list[AgentMessage],
        **_: Any,
    ) -> AgentResponse:
        """Extract the final assistant message and return it as an AgentResponse.

        Args:
            messages: The accumulated message transcript from the ReAct loop.

        Returns:
            An AgentResponse whose content is the last assistant message; finish_reason is
            'stop' when a Final Answer marker is found, otherwise 'length'.
        """
        ordered = tuple(messages)
        for message in reversed(ordered):
            if message.role == "assistant":
                content = message.content
                if self._final_answer_marker in content:
                    answer = content.split(self._final_answer_marker, 1)[1].strip()
                    return AgentResponse(content=answer, finish_reason="stop")
                return AgentResponse(content=content, finish_reason="length")
        return AgentResponse(content="", finish_reason="length")
