"""``_SampleOnce`` — draw one independent LLM sample for the same prompt."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.llm_response_text import LlmResponseText


class _SampleOnce(Knot):
    """Draw one independent sample from the LLM for the same prompt."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        # `sample_index` distinguishes the otherwise-identical fanned-out
        # invocations in lineage; the prompt sent to the LLM does not use it.
        sample_index: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prompt=prompt, llm=llm, sample_index=sample_index, _config=_config, **kwargs
        )

    async def process(self, prompt: str, llm: LLMProvider, sample_index: int, **_: Any) -> str:
        """Sample one answer to ``prompt``.

        Args:
            prompt: The user question.
            llm: The provider to sample from.
            sample_index: This sample's position; unused beyond lineage identity.

        Returns:
            The extracted answer text.
        """
        raw = await llm.chat(messages=[{"role": "user", "content": prompt}])
        return LlmResponseText().extract(raw)
