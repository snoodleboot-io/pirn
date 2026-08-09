"""``SelfRAGPipeline`` — self-reflective retrieval-augmented generation.

Generates an initial answer, then calls the LLM to assess whether
retrieval is needed, retrieves if so, and regenerates a final answer
with the retrieved context.

Stages:

1. :class:`LLMChatCall` (initial) — generate a draft answer to the query.
2. Assess whether retrieval is needed via a second :class:`LLMChatCall`.
3. Conditionally :class:`MemorySearchRetriever` + :class:`RAGPromptBuilder`
   + final :class:`LLMChatCall` when retrieval is needed.
4. :class:`RAGResponseBuilder` — wrap as :class:`AgentResponse`.

Algorithm:
    1. Receive ``query``, ``memory``, ``llm``, and ``top_k``.
    2. Validate inputs: ``query`` string, ``memory`` MemoryStore, ``llm``
       LLMProvider, ``top_k`` positive integer.
    3. Run a first inner tapestry to generate a draft answer.
    4. Run a second inner tapestry to assess (YES/NO) whether retrieval
       would improve the answer. Both need their own run because the value
       is required in Python before the next graph can be built.
    5. If YES: build retrieval, prompt, generation and response into the
       inner tapestry ``SubTapestry.__call__`` already opened, and return the
       :class:`RAGResponseBuilder` sink — so the arm's knots belong to the run
       this pipeline reports.
    6. If NO: return a :class:`RAGResponseBuilder` sink wrapping the draft.

Math:
    No quantitative computation — self-assessment is a binary LLM
    classification step with no numeric scoring.

References:
    - Asai et al., "Self-RAG: Learning to Retrieve, Generate, and
      Critique through Self-Reflection" (NeurIPS 2023):
      https://arxiv.org/abs/2310.11511
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pydantic import PositiveInt

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn_agents.specializations.rag.memory_search_retriever import (
    MemorySearchRetriever,
)
from pirn_agents.specializations.rag.rag_prompt_builder import (
    RAGPromptBuilder,
)
from pirn_agents.specializations.rag.rag_response_builder import (
    RAGResponseBuilder,
)


class SelfRAGPipeline(AgentPipeline):
    """Generate, self-assess retrieval need, optionally retrieve, then regenerate."""

    _assess_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.self_rag_pipeline.assess_prompt",
        default=(
            "Given the following question and draft answer, decide if "
            "retrieval of additional context is needed to give a more "
            "accurate or complete answer. Reply with only YES or NO.\n\n"
            "Question: {{ query }}\nDraft answer: {{ draft_answer }}"
        ),
    )

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            memory=memory,
            llm=llm,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        top_k: PositiveInt = 5,
        **_: Any,
    ) -> Any:
        """Generate a draft answer, assess retrieval need, optionally retrieve and regenerate.

        Args:
            query: The user query string to process.
            memory: The MemoryStore to search if retrieval is needed.
            llm: The LLMProvider used for draft generation, assessment, and final answer.
            top_k: The number of top memories to retrieve if retrieval is triggered.

        Returns:
            An AgentResponse containing the final LLM-generated answer.
        """
        with Tapestry() as inner_draft:
            LLMChatCall(
                prompt=query,
                llm=llm,
                _config=KnotConfig(id="draft"),
            )
        draft_result = await self._run_inner(inner_draft)
        draft_answer = draft_result.outputs.get("draft", "")

        assess_prompt = type(self)._assess_prompt.render(
            {"query": query, "draft_answer": draft_answer}
        )
        with Tapestry() as inner_assess:
            LLMChatCall(
                prompt=assess_prompt,
                llm=llm,
                _config=KnotConfig(id="assess"),
            )
        assess_result = await self._run_inner(inner_assess)
        assessment = str(assess_result.outputs.get("assess", "")).strip().upper()

        # Each arm is built into the inner tapestry `SubTapestry.__call__` has
        # already opened, and returns its real sink knot. Previously the
        # retrieval arm opened its own `with Tapestry()`, ran it via
        # `_run_inner`, pulled the answer out, and handed back a `_ResultSource`
        # closure wrapping the precomputed value — so the arm's knots were
        # invisible to the run this pipeline reports.
        if "YES" in assessment:
            retrieved = MemorySearchRetriever(
                store=memory,
                query=query,
                top_k=top_k,
                _config=KnotConfig(id="retrieve"),
            )
            prompt = RAGPromptBuilder(
                query=query,
                retrieved=retrieved,
                _config=KnotConfig(id="prompt"),
            )
            answer = LLMChatCall(
                prompt=prompt,
                llm=llm,
                _config=KnotConfig(id="generate"),
            )
            return RAGResponseBuilder(answer=answer, _config=KnotConfig(id="response"))

        # The draft is always a string: `outputs.get("draft", "")` defaults to
        # one and `LLMChatCall` returns `_extract_text`'s str. The old
        # `finish_reason="length"` fallback for a non-str draft was therefore
        # unreachable, and no test covered it; the coercion is kept so the
        # behaviour is identical on every reachable path.
        content = draft_answer if isinstance(draft_answer, str) else ""
        return RAGResponseBuilder(
            answer=content,  # pyright: ignore[reportArgumentType]
            _config=KnotConfig(id="direct_response"),
        )
