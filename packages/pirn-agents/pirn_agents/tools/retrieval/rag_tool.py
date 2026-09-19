"""``RagTool`` — retrieval-augmented generation behind a single tool call.

Composes a bound :class:`~pirn_agents.memory.stores.memory_store.MemoryStore` (retrieval)
and a bound :class:`~pirn_agents.llm.llm_provider.LLMProvider` (generation)
so an agent can call RAG as one explicit tool — the seed for F9's agentic RAG.
Provider-neutral for both the store and the LLM; no vendor SDK is imported at
module load.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.agent.recorded_llm_call import RecordedLlmCall
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.tools.tool import Tool


class RagTool(Tool):
    """Answer a question with retrieval-augmented generation over the knowledge store."""

    tool_name: ClassVar[str] = "rag"

    _system_prompt_binding: ClassVar[PromptBinding] = PromptBinding(
        name="tools.retrieval.rag_tool.system_prompt_binding",
        default=(
            "Answer the question using only the provided context. "
            "If the context is insufficient, say so."
        ),
    )

    def __init__(
        self,
        *,
        question: Knot | str,
        store: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        top_k: Knot | int = 5,
        model: Knot | str | None = None,
        system_prompt: Knot | str | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            question=question,
            store=store,
            llm=llm,
            top_k=top_k,
            model=model,
            system_prompt=system_prompt,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        question: Annotated[str, Field(description="The question to answer.")],
        store: MemoryStore,
        llm: LLMProvider,
        top_k: int = 5,
        model: str | None = None,
        system_prompt: str | None = None,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Retrieve context, prompt the LLM, and return the answer plus sources.

        Args:
            question: The question to answer.
            store: The :class:`MemoryStore` providing context; bound once.
            llm: The :class:`LLMProvider` generating the answer; bound once.
            top_k: Number of context records retrieved per question.
            model: Optional model identifier forwarded to the LLM.
            system_prompt: Optional system instruction prepended to the prompt.

        Returns:
            ``{"question", "answer", "sources": [mapping...]}``.

        Raises:
            ValueError: If ``question`` is empty or ``top_k`` is not positive.
        """
        if not question:
            raise ValueError("rag: 'question' must be a non-empty string")
        if top_k <= 0:
            raise ValueError(f"rag: top_k must be positive, got {top_k}")
        hits = await store.search(question, top_k=top_k)
        sources = [dict(item) for item in list(hits)[:top_k]]
        context = self._format_context(sources)
        messages = [
            {
                "role": "system",
                "content": type(self)._system_prompt_binding.resolve(system_prompt or None),
            },
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ]
        response = await RecordedLlmCall.chat(
            knot_id=self.knot_id, llm=llm, messages=messages, model=model
        )
        answer = LlmResponseText().extract(response)
        return {"question": question, "answer": answer, "sources": sources}

    @staticmethod
    def _format_context(sources: list[dict[str, Any]]) -> str:
        """Render retrieved records into a numbered context block for the prompt."""
        lines: list[str] = []
        for index, source in enumerate(sources, start=1):
            text = source.get("text") or source.get("content") or source
            lines.append(f"[{index}] {text}")
        return "\n".join(lines) if lines else "(no context retrieved)"
