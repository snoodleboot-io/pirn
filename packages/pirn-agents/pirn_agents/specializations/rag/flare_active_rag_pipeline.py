"""``FlareActiveRagPipeline`` — forward-looking active retrieval (FLARE).

FLARE generates the answer one sentence at a time. Each candidate sentence comes
with a confidence; when a sentence is low-confidence, the pipeline pauses, uses
that tentative sentence as a search query, retrieves evidence, and regenerates
the sentence grounded in what it found — retrieving *forward* only when the model
is unsure. Retrieval calls are hard-bounded by ``max_retrieval_calls``.

Algorithm:
    1. Validate ``query`` (str), ``memory`` (:class:`MemoryStore`), ``llm``
       (:class:`LLMProvider`), and the numeric budgets.
    2. Repeat up to ``max_sentences``:
       a. Ask the LLM for the next sentence as ``DONE`` or ``CONF=<f>: <text>``.
       b. Parse the confidence and sentence; stop on ``DONE``.
       c. If :class:`SentenceConfidenceMonitor` flags it and the retrieval budget
          remains, retrieve on the tentative sentence and regenerate it grounded
          in the evidence.
       d. Append the (possibly regenerated) sentence to the answer.
    3. Return the assembled answer as an :class:`AgentResponse`.

References:
    - Jiang et al., "Active Retrieval Augmented Generation" (FLARE, EMNLP 2023):
      https://arxiv.org/abs/2305.06983
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.sentence_confidence_monitor import SentenceConfidenceMonitor
from pirn_agents.types.agent_response import AgentResponse


class FlareActiveRagPipeline(SubTapestry):
    """Generate sentence-by-sentence, retrieving forward on low confidence."""

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        confidence_threshold: Knot | float = 0.5,
        max_sentences: Knot | int = 5,
        max_retrieval_calls: Knot | int = 3,
        top_k: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            memory=memory,
            llm=llm,
            confidence_threshold=confidence_threshold,
            max_sentences=max_sentences,
            max_retrieval_calls=max_retrieval_calls,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        confidence_threshold: float = 0.5,
        max_sentences: int = 5,
        max_retrieval_calls: int = 3,
        top_k: int = 3,
        **_: Any,
    ) -> Any:
        """Run the FLARE loop and return the assembled answer as a source knot.

        Args:
            query: The question to answer.
            memory: The memory store searched on low-confidence sentences.
            llm: The provider generating and regenerating sentences.
            confidence_threshold: Confidence below which retrieval fires.
            max_sentences: Hard cap on generated sentences.
            max_retrieval_calls: Hard cap on retrieval calls.
            top_k: Hits fetched per retrieval.

        Returns:
            A source knot whose output is the final :class:`AgentResponse`.

        Raises:
            TypeError: If ``query``/``memory``/``llm`` are the wrong type.
            ValueError: If any budget is not a positive integer.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"FlareActiveRagPipeline: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                f"FlareActiveRagPipeline: memory must be a MemoryStore, got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"FlareActiveRagPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(max_sentences, int) or max_sentences <= 0:
            raise ValueError(
                f"FlareActiveRagPipeline: max_sentences must be a positive int, got {max_sentences!r}"
            )
        if not isinstance(max_retrieval_calls, int) or max_retrieval_calls <= 0:
            raise ValueError(
                "FlareActiveRagPipeline: max_retrieval_calls must be a positive int, "
                f"got {max_retrieval_calls!r}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"FlareActiveRagPipeline: top_k must be a positive int, got {top_k!r}")
        parts: list[str] = []
        retrieval_calls = 0
        for _step in range(max_sentences):
            reply = self._extract_text(
                await llm.chat([{"role": "user", "content": self._generate_prompt(query, parts)}])
            )
            reply = reply.strip()
            if reply.upper().startswith("DONE"):
                break
            confidence, sentence = self._parse(reply)
            if (
                SentenceConfidenceMonitor.needs_retrieval(confidence, float(confidence_threshold))
                and retrieval_calls < max_retrieval_calls
            ):
                docs = await self._search(memory, sentence, top_k)
                retrieval_calls += 1
                sentence = self._extract_text(
                    await llm.chat(
                        [
                            {
                                "role": "user",
                                "content": self._regenerate_prompt(query, sentence, docs),
                            }
                        ]
                    )
                ).strip()
            if sentence:
                parts.append(sentence)
        answer = " ".join(parts)
        final = AgentResponse(content=answer, finish_reason="stop")

        class _ResultSource(Source):
            async def process(self, **_: Any) -> AgentResponse:
                return final

        return _ResultSource(_config=KnotConfig(id="result"))

    @staticmethod
    def _generate_prompt(query: str, parts: list[str]) -> str:
        """Prompt the LLM for the next sentence with a confidence tag."""
        so_far = " ".join(parts) if parts else "(nothing yet)"
        return (
            "Answer the question one sentence at a time. Reply with 'DONE' if the answer is "
            "complete, otherwise reply exactly 'CONF=<0-1>: <the next sentence>' where the number "
            f"is your confidence.\n\nQuestion: {query}\n\nAnswer so far: {so_far}"
        )

    @staticmethod
    def _regenerate_prompt(query: str, sentence: str, docs: list[Mapping[str, Any]]) -> str:
        """Prompt the LLM to rewrite a tentative sentence grounded in evidence."""
        context = "\n".join(str(doc) for doc in docs) or "(no evidence retrieved)"
        return (
            "Rewrite the tentative sentence so it is fully supported by the evidence. Reply with "
            f"only the corrected sentence.\n\nQuestion: {query}\n\nTentative sentence: {sentence}\n\n"
            f"Evidence:\n{context}"
        )

    @staticmethod
    def _parse(reply: str) -> tuple[float, str]:
        """Parse a ``CONF=<f>: <sentence>`` reply into ``(confidence, sentence)``."""
        match = re.match(r"\s*CONF\s*=\s*([01](?:\.\d+)?)\s*:\s*(.*)", reply, flags=re.DOTALL)
        if match is None:
            return 1.0, reply
        confidence = float(match.group(1))
        confidence = min(1.0, max(0.0, confidence))
        return confidence, match.group(2).strip()

    @staticmethod
    async def _search(store: MemoryStore, query: str, top_k: int) -> list[Mapping[str, Any]]:
        """Drain ``store.search`` (awaitable / async-iterable / list) into a list."""
        candidate = store.search(query, top_k=top_k)
        if hasattr(candidate, "__await__"):
            candidate = await candidate  # type: ignore[assignment]
        if hasattr(candidate, "__aiter__"):
            collected: list[Mapping[str, Any]] = []
            async for item in candidate:  # type: ignore[misc]
                collected.append(item)
                if len(collected) >= top_k:
                    break
            return collected
        if isinstance(candidate, list):
            return list(candidate[:top_k])
        return [item for item in candidate][:top_k]  # type: ignore[misc]

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
