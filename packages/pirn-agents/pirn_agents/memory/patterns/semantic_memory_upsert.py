# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``SemanticMemoryUpsert`` — extract and deduplicate facts from an :class:`AgentResponse`.

Extracts factual claims from an :class:`AgentResponse` via an LLM, checks
each candidate fact against existing semantic memory, and upserts only
new facts into a :class:`~pirn_agents.memory.stores.keyed_lineage_store.KeyedLineageStore`.

Algorithm
---------
1. Validate inputs.
2. Build a prompt from ``fact_extraction_prompt`` and ``response.content``.
3. Call the LLM and parse one fact per line.
4. For each fact, check whether it is already recorded (see "Dedup" below).
5. If not, ``store.put`` a typed
   :class:`~pirn_agents.memory.management.memory_record.MemoryRecord` payload;
   increment the counter.
6. Return the total count of upserted facts.

Dedup (ADR "agents speaks core" WS3 part 4)
--------------------------------------------
A keyed identity is a knot id, not a KV slot: each fact's identity is
``pirn.core.content_hasher.ContentHasher.hash(fact)`` itself — the *same* fact text always
maps to the *same* identity. That makes "has this fact already been recorded"
a single, cheap ``RunHistory`` lookup
(:meth:`~pirn_agents.memory.stores.keyed_lineage_store.KeyedLineageStore.latest_output_hash`)
with no need to fetch or parse the previously-stored value: a row already
existing at that identity **is** the dedup signal, because the identity itself
already encodes the candidate's content hash. This sidesteps a trap the
naive reading of "compare content hashes" falls into — comparing the hash of
a *freshly built* ``MemoryRecord`` (whose ``created_at`` is always "now") to a
previously stored one would never match, since the timestamp always differs,
defeating dedup entirely. Comparing by identity-existence rather than by
rehashing a fresh candidate avoids that trap while still reading as "compare
the candidate's content hash against what's on record".

References
----------
None.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from pirn.core.content_hasher import ContentHasher
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.management.memory_provenance import MemoryProvenance
from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.stores.keyed_lineage_store import KeyedLineageStore
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.types.messaging.agent_response import AgentResponse


class SemanticMemoryUpsert(Knot):
    """Extract facts from an AgentResponse, deduplicate, and upsert to semantic memory."""

    _fact_extraction_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="memory.patterns.semantic_memory_upsert.fact_extraction_prompt",
        default="Extract key facts from the following text.",
    )
    _namespace: ClassVar[str] = "semantic-memory"

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        llm: Knot | LLMProvider,
        store: Knot | KeyedLineageStore,
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
        store: KeyedLineageStore,
        fact_extraction_prompt: str = _fact_extraction_prompt.default,
        **_: Any,
    ) -> int:
        """Extract facts from the response, deduplicate against memory, and upsert new facts.

        Args:
            response: The AgentResponse whose content is mined for factual claims.
            llm: The LLMProvider used to extract facts.
            store: The KeyedLineageStore for deduplication lookups and writes.
            fact_extraction_prompt: Non-empty prompt string prefixed to the extraction request.

        Returns:
            The number of new facts upserted into semantic memory.

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

        namespace = type(self)._namespace
        upserted = 0
        for fact in facts:
            key = ContentHasher.hash(fact)
            already_recorded = (
                await store.latest_output_hash(namespace=namespace, key=key) is not None
            )
            if not already_recorded:
                now = datetime.now(UTC)
                record = MemoryRecord(
                    id=f"fact:{key}",
                    kind="semantic",
                    content=fact,
                    provenance=MemoryProvenance(source="semantic_memory_upsert", timestamp=now),
                    created_at=now,
                )
                await store.put(namespace=namespace, key=key, value=record.to_payload())
                upserted += 1
        return upserted
