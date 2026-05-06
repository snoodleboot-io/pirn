"""``RAGResponseBuilder`` — wrap an LLM answer string as :class:`AgentResponse`.

Algorithm:
    1. Receive the LLM-generated ``answer`` string.
    2. Validate that ``answer`` is a string.
    3. Construct and return an :class:`AgentResponse` with
       ``content=answer`` and ``finish_reason="stop"``.

Math:
    No quantitative computation — this is a pure wrapping step.

References:
    - :class:`AgentResponse` dataclass in
      ``pirn.domains.agents.types.agent_response``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


class RAGResponseBuilder(Knot):
    """Wraps an LLM answer string as an :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        answer: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(answer=answer, _config=_config, **kwargs)

    async def process(self, answer: str, **_: Any) -> AgentResponse:
        """Wrap the LLM answer string in an AgentResponse with finish_reason 'stop'.

        Args:
            answer: The LLM-generated answer text to package as response content.

        Returns:
            An AgentResponse with the answer as content and finish_reason set to 'stop'.

        Raises:
            TypeError: If answer is not a string.
        """
        if not isinstance(answer, str):
            raise TypeError(
                f"RAGResponseBuilder: answer must be a string, got {type(answer).__name__}"
            )
        return AgentResponse(content=answer, finish_reason="stop")
