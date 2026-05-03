"""``SemanticMemoryPipeline`` — extract facts via LLM and persist them.

A :class:`SubTapestry` that composes:

1. :class:`SemanticFactExtractor` — asks the LLM to enumerate the
   factual claims contained in the supplied messages.
2. :class:`SemanticFactWriter` — stores each fact under a deterministic
   hash-keyed entry in the :class:`MemoryStore`.

Returns the number of facts written.
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
        llm: LLMProvider,
        store: MemoryStore,
        _config: KnotConfig,
        fact_extraction_prompt: str = (
            "Extract key facts from the following conversation."
        ),
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "SemanticMemoryPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "SemanticMemoryPipeline: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        if (
            not isinstance(fact_extraction_prompt, str)
            or not fact_extraction_prompt
        ):
            raise ValueError(
                "SemanticMemoryPipeline: fact_extraction_prompt must be a "
                "non-empty string"
            )
        self._llm = llm
        self._store = store
        self._fact_prompt = fact_extraction_prompt
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: Sequence[AgentMessage],
        **_: Any,
    ) -> int:
        """Extract factual claims from messages via the LLM and persist them, returning the count written.

        Args:
            messages: The sequence of agent messages to extract semantic facts from.

        Returns:
            The number of facts extracted and persisted.

        Raises:
            RuntimeError: If the inner write knot does not return a count.
        """
        seed_messages = tuple(messages)
        with Tapestry() as inner:
            facts = SemanticFactExtractor(
                messages=seed_messages,
                llm=self._llm,
                fact_extraction_prompt=self._fact_prompt,
                _config=KnotConfig(id="extract"),
            )
            SemanticFactWriter(
                facts=facts,
                store=self._store,
                _config=KnotConfig(id="write"),
            )
        inner_result = await self._run_inner(inner)
        count = inner_result.outputs.get("write")
        if not isinstance(count, int):
            raise RuntimeError(
                "SemanticMemoryPipeline: inner write did not return a count"
            )
        return count
