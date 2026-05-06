"""``SemanticMemoryPipeline`` — extract facts via LLM and persist them.

A :class:`SubTapestry` that composes:

1. :class:`SemanticFactExtractor` — asks the LLM to enumerate the
   factual claims contained in the supplied messages.
2. :class:`SemanticFactWriter` — stores each fact under a deterministic
   hash-keyed entry in the :class:`MemoryStore`.

Returns the number of facts written.

Algorithm
---------
1. Validate inputs.
2. Construct an inner Tapestry chaining extractor → writer.
3. Run the inner tapestry via ``self._run_inner(inner)``.
4. Extract and return the count of facts written.

Math
----
No mathematical operations.

References
----------
None.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.memory_patterns.semantic_fact_extractor import (
    SemanticFactExtractor,
)
from pirn.domains.agents.specializations.memory_patterns.semantic_fact_writer import (
    SemanticFactWriter,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class SemanticMemoryPipeline(SubTapestry):
    """Extract facts from messages and store them as semantic memories."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        llm: Knot | LLMProvider,
        store: Knot | MemoryStore,
        fact_extraction_prompt: Knot | str = ("Extract key facts from the following conversation."),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            messages=messages,
            llm=llm,
            store=store,
            fact_extraction_prompt=fact_extraction_prompt,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        messages: Sequence[AgentMessage],
        llm: LLMProvider,
        store: MemoryStore,
        fact_extraction_prompt: str = "Extract key facts from the following conversation.",
        **_: Any,
    ) -> int:
        """Extract factual claims from messages via the LLM and persist them, returning the count written.

        Args:
            messages: The sequence of agent messages to extract semantic facts from.
            llm: The LLMProvider used for fact extraction.
            store: The MemoryStore to persist facts into.
            fact_extraction_prompt: Non-empty prompt string prefixed to the extraction request.

        Returns:
            The number of facts extracted and persisted.

        Raises:
            TypeError: If llm is not an LLMProvider or store is not a MemoryStore.
            ValueError: If fact_extraction_prompt is not a non-empty string.
            RuntimeError: If the inner write knot does not return a count.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SemanticMemoryPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"SemanticMemoryPipeline: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(fact_extraction_prompt, str) or not fact_extraction_prompt:
            raise ValueError(
                "SemanticMemoryPipeline: fact_extraction_prompt must be a non-empty string"
            )
        seed_messages = tuple(messages)
        with Tapestry() as inner:
            facts = SemanticFactExtractor(
                messages=seed_messages,
                llm=llm,
                fact_extraction_prompt=fact_extraction_prompt,
                _config=KnotConfig(id="extract"),
            )
            SemanticFactWriter(
                facts=facts,
                store=store,
                _config=KnotConfig(id="write"),
            )
        inner_result = await self._run_inner(inner)
        count = inner_result.outputs.get("write")
        if not isinstance(count, int):
            raise RuntimeError("SemanticMemoryPipeline: inner write did not return a count")
        return count
