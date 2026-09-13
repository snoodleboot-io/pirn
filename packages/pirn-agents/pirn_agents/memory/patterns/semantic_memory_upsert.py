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
5. If absent or changed, call ``store.store`` with a typed
   :class:`~pirn_agents.memory.management.memory_record.MemoryRecord` payload;
   increment the counter.
6. Return the total count of upserted facts.

Math
----
Key: ``"fact:" + sha256(fact)[:16]``.

ADR "agents speaks core" WS3 part 3 note: this still writes through
:class:`MemoryStore` (typically backed by
:class:`~pirn_agents.memory.stores.data_store_memory_store.DataStoreMemoryStore`)
rather than the ``Payload``-returning writer-knot pattern
:class:`~pirn_agents.memory.memory_lineage_recall.MemoryLineageRecall` reads
back — deduplication needs a lookup *by the fact's own key* before a value
exists to hash, which lineage-by-knot-id recall does not provide. What moved
is the payload shape: the stored value is now a typed
:class:`~pirn_agents.memory.management.memory_record.MemoryRecord`, not a
bare ``{"fact": ...}`` dict.

References
----------
None.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.management.memory_provenance import MemoryProvenance
from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.types.messaging.agent_response import AgentResponse


class SemanticMemoryUpsert(Knot):
    """Extract facts from an AgentResponse, deduplicate, and upsert to semantic memory."""

    _fact_extraction_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="memory.patterns.semantic_memory_upsert.fact_extraction_prompt",
        default="Extract key facts from the following text.",
    )

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        llm: Knot | LLMProvider,
        store: Knot | MemoryStore,
        fact_extraction_prompt: Knot | str = _fact_extraction_prompt.default,
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
        fact_extraction_prompt: str = _fact_extraction_prompt.default,
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
            ValueError: If fact_extraction_prompt is not a non-empty string.
        """
        if not isinstance(fact_extraction_prompt, str) or not fact_extraction_prompt:
            raise ValueError(
                "SemanticMemoryUpsert: fact_extraction_prompt must be a non-empty string"
            )
        instruction = type(self)._fact_extraction_prompt.resolve(fact_extraction_prompt)
        prompt = f"{instruction}\n\nText: {response.content}\n\nReturn one fact per line."
        raw = await llm.chat([{"role": "user", "content": prompt}])
        text = LlmResponseText().extract(raw)
        facts: list[str] = []
        for raw_line in text.splitlines():
            cleaned = raw_line.strip()
            if not cleaned:
                continue
            for marker in ("- ", "* ", "• "):
                if cleaned.startswith(marker):
                    cleaned = cleaned[len(marker) :].strip()
                    break
            if cleaned:
                facts.append(cleaned)

        upserted = 0
        for fact in facts:
            key = "fact:" + hashlib.sha256(fact.encode()).hexdigest()[:16]
            existing = await store.retrieve(key)
            if existing is None or self._content_of(existing) != fact:
                now = datetime.now(UTC)
                record = MemoryRecord(
                    id=key,
                    kind="semantic",
                    content=fact,
                    provenance=MemoryProvenance(source="semantic_memory_upsert", timestamp=now),
                    created_at=now,
                )
                await store.store(key, record.to_payload())
                upserted += 1
        return upserted

    @staticmethod
    def _content_of(existing: Any) -> str | None:
        """Return the fact text from an existing entry, old or new payload shape.

        Reads the current ``MemoryRecord.to_payload()`` shape (``"content"``)
        and falls back to the pre-migration flat shape (``{"fact": ...}``) so
        an already-persisted entry written before this change still
        deduplicates correctly.
        """
        if not isinstance(existing, dict):
            return None
        if "content" in existing:
            return str(existing["content"])
        fact = existing.get("fact")
        return str(fact) if fact is not None else None
