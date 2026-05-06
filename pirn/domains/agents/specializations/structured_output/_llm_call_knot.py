"""``_LLMCallKnot`` — internal single-prompt LLM call knot for RetryOnParseFailure.

Algorithm:
    1. Receive ``prompt`` (string) and ``llm`` provider.
    2. Frame the prompt as a single user chat message.
    3. Call the LLM provider and extract the text content from the response.
    4. Return the extracted text string.


References:
    - :class:`pirn.domains.agents.llm_provider.LLMProvider`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class _LLMCallKnot(Knot):
    """Inner knot that calls the LLM with a single prompt string."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(prompt=prompt, llm=llm, _config=_config, **kwargs)

    async def process(self, prompt: str, llm: LLMProvider, **_: Any) -> str:
        """Call the LLM and return the text content of the response.

        Args:
            prompt: The prompt string sent to the LLM as a user message.
            llm: The LLM provider to call.

        Returns:
            The text content returned by the LLM.
        """
        raw = await llm.chat([{"role": "user", "content": prompt}])
        return self._extract_text(raw)

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
