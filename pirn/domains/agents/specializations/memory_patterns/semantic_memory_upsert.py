"""``SemanticMemoryUpsert`` — extract and deduplicate facts from an :class:`AgentResponse`.

Extracts factual claims from an :class:`AgentResponse` via an LLM, checks
each candidate fact against existing semantic memory, and upserts only
new or changed facts into the :class:`MemoryStore`.
"""

from __future__ import annotations

import hashlib
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.types.agent_response import AgentResponse


class SemanticMemoryUpsert(Knot):
    """Extract facts from an AgentResponse, deduplicate, and upsert to semantic memory."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        llm: LLMProvider,
        store: MemoryStore,
        _config: KnotConfig,
        fact_extraction_prompt: str = (
            "Extract key facts from the following text."
        ),
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "SemanticMemoryUpsert: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "SemanticMemoryUpsert: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(fact_extraction_prompt, str) or not fact_extraction_prompt:
            raise ValueError(
                "SemanticMemoryUpsert: fact_extraction_prompt must be a "
                "non-empty string"
            )
        self._llm = llm
        self._store = store
        self._fact_prompt = fact_extraction_prompt
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        **_: Any,
    ) -> int:
        """Extract facts from the response, deduplicate against memory, and upsert new facts.

        Args:
            response: The AgentResponse whose content is mined for factual claims.

        Returns:
            The number of new or changed facts upserted into the memory store.

        Raises:
            TypeError: If response is not an AgentResponse.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "SemanticMemoryUpsert: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        prompt = (
            f"{self._fact_prompt}\n\n"
            f"Text: {response.content}\n\n"
            "Return one fact per line."
        )
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
        text = self._extract_text(raw)
        facts: list[str] = []
        for raw_line in text.splitlines():
            cleaned = raw_line.strip()
            if not cleaned:
                continue
            for marker in ("- ", "* ", "• "):
                if cleaned.startswith(marker):
                    cleaned = cleaned[len(marker):].strip()
                    break
            if cleaned:
                facts.append(cleaned)

        upserted = 0
        for fact in facts:
            key = "fact:" + hashlib.sha256(fact.encode()).hexdigest()[:16]
            existing = await self._store.retrieve(key)
            if existing is None or existing.get("fact") != fact:
                await self._store.store(key, {"fact": fact})
                upserted += 1
        return upserted

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
