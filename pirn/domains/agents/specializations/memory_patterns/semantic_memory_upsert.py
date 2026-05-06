"""``SemanticMemoryUpsert`` — extract and deduplicate facts from an :class:`AgentResponse`.

Extracts factual claims from an :class:`AgentResponse` via an LLM, checks
each candidate fact against existing semantic memory, and upserts only
new or changed facts into the :class:`MemoryStore`.

Algorithm
---------
1. Validate inputs.
2. Build a prompt from ``fact_extraction_prompt`` and ``response.content``.
3. Call the LLM and parse one fact per line.
4. For each fact compute a SHA-256 prefix key; retrieve the existing entry.
5. If absent or changed, call ``store.store``; increment the counter.
6. Return the total count of upserted facts.

Math
----
Key: ``"fact:" + sha256(fact)[:16]``.

References
----------
None.
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
        llm: Knot | LLMProvider,
        store: Knot | MemoryStore,
        fact_extraction_prompt: Knot | str = (
            "Extract key facts from the following text."
        ),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            response=response,
            llm=llm,
            store=store,
            fact_extraction_prompt=fact_extraction_prompt,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        llm: LLMProvider,
        store: MemoryStore,
        fact_extraction_prompt: str = "Extract key facts from the following text.",
        **_: Any,
    ) -> int:
        """Extract facts from the response, deduplicate against memory, and upsert new facts.

        Args:
            response: The AgentResponse whose content is mined for factual claims.
            llm: The LLMProvider used to extract facts.
            store: The MemoryStore for deduplication lookups and writes.
            fact_extraction_prompt: Non-empty prompt string prefixed to the extraction request.

        Returns:
            The number of new or changed facts upserted into the memory store.

        Raises:
            TypeError: If response is not an AgentResponse, llm is not an LLMProvider,
                or store is not a MemoryStore.
            ValueError: If fact_extraction_prompt is not a non-empty string.
        """
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
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "SemanticMemoryUpsert: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        prompt = (
            f"{fact_extraction_prompt}\n\n"
            f"Text: {response.content}\n\n"
            "Return one fact per line."
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
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
            existing = await store.retrieve(key)
            if existing is None or existing.get("fact") != fact:
                await store.store(key, {"fact": fact})
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
