"""``_LLMCallKnot`` — internal single-prompt LLM call knot for RetryOnParseFailure."""

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
        prompt: str,
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._prompt = prompt
        self._llm = llm
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        """Call the LLM and return the text content of the response.

        Returns:
            The text content returned by the LLM.
        """
        raw = await self._llm.chat(
            [{"role": "user", "content": self._prompt}]
        )
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
