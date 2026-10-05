"""``SemanticMemoryUpsert`` — extract and deduplicate facts from an :class:`AgentResponse`.

Extracts factual claims from an :class:`AgentResponse` via an LLM, checks
each candidate fact against existing semantic memory, and upserts only
new facts into a :class:`~pirn_agents.memory.stores.keyed_lineage_store.KeyedLineageStore`.

Algorithm
---------
1. Validate inputs.
2. Build a prompt from ``fact_extraction_prompt`` and ``response.data``.
3. Call the LLM and parse one fact per line, collapsing repeats.
4. Declare one
   :class:`~pirn_agents.memory.patterns.deduplicated_semantic_fact.DeduplicatedSemanticFact`
   per candidate and run them as an inner tapestry: each checks whether its
   fact is already recorded (see "Dedup" below) and, if not, ``store.put`` s a
   typed :class:`~pirn_agents.memory.management.memory_record.MemoryRecord`
   payload.
5. Return the count of knots that reported a write.

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

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.nested_run_knot import NestedRunKnot
from pirn.tapestry import Tapestry

from pirn_agents.agent.recorded_llm_call import RecordedLlmCall
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.patterns.deduplicated_semantic_fact import DeduplicatedSemanticFact
from pirn_agents.memory.stores.keyed_lineage_store import KeyedLineageStore
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.types.messaging.agent_response import AgentResponse


class SemanticMemoryUpsert(NestedRunKnot):
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
        prompt = f"{instruction}\n\nText: {response.data}\n\nReturn one fact per line."
        raw = await RecordedLlmCall.chat(
            knot_id=self.knot_id,
            llm=llm,
            messages=({"role": "user", "content": prompt},),
        )
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

        # One extraction can name the same fact twice. The dedup reads below run
        # concurrently, so two knots for one identity would both see "absent"
        # and both write; collapsing repeats here makes the outcome the same as
        # the sequential loop's, and cheaper (no store round-trip for a repeat).
        unique_facts = list(dict.fromkeys(facts))
        if not unique_facts:
            return 0
        # One knot per candidate fact, run together: each dedup read and each
        # write gets its own Result, retry, timeout and lineage row, and the
        # engine schedules them rather than a Python loop awaiting the store N
        # times (Rule 11; PIR-874). The extraction call above is one request, so
        # it stays as it is.
        namespace = type(self)._namespace
        stored_at = datetime.now(UTC)
        with Tapestry() as inner:
            store_node = Parameter(
                "store", KeyedLineageStore, default=store, _config=KnotConfig(id="store")
            )
            per_fact: dict[str, Knot] = {
                f"fact_{index}": DeduplicatedSemanticFact(
                    fact=fact,
                    namespace=namespace,
                    store=store_node,
                    stored_at=stored_at,
                    _config=KnotConfig(id=f"fact_{index}"),
                )
                for index, fact in enumerate(unique_facts)
            }
            Aggregator(
                combine=SemanticMemoryUpsert._count_written,
                _config=KnotConfig(id="upserted"),
                **per_fact,
            )
        run = await self._run_inner(inner)
        return run.outputs["upserted"]

    @staticmethod
    def _count_written(**facts: str | None) -> int:
        """Count the per-fact knots that returned a key rather than ``None``."""
        return sum(1 for key in facts.values() if key is not None)
