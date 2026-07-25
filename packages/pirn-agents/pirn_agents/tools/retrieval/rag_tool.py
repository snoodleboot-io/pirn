"""``RagTool`` — retrieval-augmented generation behind a single tool call.

Composes an injected :class:`~pirn_agents.memory_store.MemoryStore` (retrieval)
and an injected :class:`~pirn_agents.llm_provider.LLMProvider` (generation)
so an agent can call RAG as one explicit tool — the seed for F9's agentic RAG.
Provider-neutral for both the store and the LLM; no vendor SDK is imported at
module load.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.memory_store import MemoryStore
from pirn_agents.tools.base_tool import BaseTool


class RagTool(BaseTool):
    """Answer a question by retrieving context and prompting an LLM with it."""

    def __init__(
        self,
        *,
        store: MemoryStore,
        llm: LLMProvider,
        top_k: int = 5,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        """Bind the tool to a store, an LLM, and generation defaults.

        Args:
            store: The injected :class:`MemoryStore` providing context.
            llm: The injected :class:`LLMProvider` generating the answer.
            top_k: Number of context records retrieved per question.
            model: Optional model identifier forwarded to the LLM.
            system_prompt: Optional system instruction prepended to the prompt.

        Raises:
            TypeError: If ``store``/``llm`` are not the expected interfaces.
            ValueError: If ``top_k`` is not positive.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(f"rag: store must be a MemoryStore, got {type(store).__name__}")
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"rag: llm must be an LLMProvider, got {type(llm).__name__}")
        if top_k <= 0:
            raise ValueError(f"rag: top_k must be positive, got {top_k}")
        self._store: MemoryStore = store
        self._llm: LLMProvider = llm
        self._top_k = top_k
        self._model = model
        self._system_prompt = system_prompt or (
            "Answer the question using only the provided context. "
            "If the context is insufficient, say so."
        )

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"rag"``."""
        return "rag"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return "Answer a question with retrieval-augmented generation over the knowledge store."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the ``question`` argument."""
        return {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to answer."}
            },
            "required": ["question"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Retrieve context, prompt the LLM, and return the answer plus sources.

        Returns:
            ``{"question", "answer", "sources": [mapping...]}``.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If ``question`` is missing/empty.
        """
        self._require_mapping(self.name, arguments)
        question = self._string_argument(self.name, arguments, "question")
        sources = await self._collect(question)
        context = self._format_context(sources)
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ]
        response = await self._llm.chat(messages, model=self._model)
        answer = _extract_text(response)
        return {"question": question, "answer": answer, "sources": sources}

    async def _collect(self, question: str) -> list[dict[str, Any]]:
        """Drain the store's async search iterator into an ordered list."""
        iterator = await self._store.search(question, top_k=self._top_k)
        collected: list[dict[str, Any]] = []
        async for item in iterator:
            collected.append(dict(item))
            if len(collected) >= self._top_k:
                break
        return collected

    @staticmethod
    def _format_context(sources: list[dict[str, Any]]) -> str:
        """Render retrieved records into a numbered context block for the prompt."""
        lines: list[str] = []
        for index, source in enumerate(sources, start=1):
            text = source.get("text") or source.get("content") or source
            lines.append(f"[{index}] {text}")
        return "\n".join(lines) if lines else "(no context retrieved)"

    def _clear_credentials(self) -> None:
        """Drop the store and LLM references so they become garbage-collectable."""
        self._store = None  # type: ignore[assignment]
        self._llm = None  # type: ignore[assignment]


def _extract_text(response: Mapping[str, Any]) -> str:
    """Extract assistant text from a provider-neutral chat response mapping."""
    content = response.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, Mapping):
            text = first.get("text")
            if isinstance(text, str):
                return text
        if isinstance(first, str):
            return first
    text = response.get("text")
    if isinstance(text, str):
        return text
    return str(response)
