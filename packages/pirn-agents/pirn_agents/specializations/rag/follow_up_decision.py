"""``FollowUpDecision`` — ask the LLM whether the tool's answer suffices."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.tools.tool_result import ToolResult


class FollowUpDecision(Knot):
    """Ask the LLM whether the tool's answer resolves the original question."""

    _next_question_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.agentic_rag_pipeline.next_question_prompt",
        default=(
            "You are an agent answering a question with a retrieval tool. Given the "
            "original question and the tool's latest answer, reply with exactly 'DONE' if "
            "the answer fully resolves the question, or 'FOLLOWUP: <a more specific "
            "question>' otherwise.\n\nOriginal question: {{ query }}\n\n"
            "Latest answer: {{ answer }}"
        ),
    )

    def __init__(
        self,
        *,
        original_query: Knot | str,
        tool_result: Knot | ToolResult,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            original_query=original_query,
            tool_result=tool_result,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        original_query: str,
        tool_result: ToolResult,
        llm: LLMProvider,
        **_: Any,
    ) -> str | None:
        """Ask the LLM for a follow-up question, or ``None`` when the answer suffices."""
        answer = FollowUpDecision.tool_answer(tool_result.result)
        return await FollowUpDecision.next_question(llm, original_query, answer)

    @staticmethod
    async def next_question(llm: LLMProvider, query: str, answer: str) -> str | None:
        """Ask the LLM for a follow-up question, or ``None`` when the answer suffices.

        Args:
            llm: The provider making the decision.
            query: The original question.
            answer: The tool's latest answer.

        Returns:
            The follow-up question on a ``FOLLOWUP:`` reply, otherwise ``None``.
        """
        prompt = FollowUpDecision._next_question_prompt.render({"query": query, "answer": answer})
        raw = await llm.chat([{"role": "user", "content": prompt}])
        reply = LlmResponseText().extract(raw).strip()
        if reply.upper().startswith("FOLLOWUP:"):
            follow_up = reply.split(":", 1)[1].strip()
            return follow_up or None
        return None

    @staticmethod
    def tool_answer(result: object) -> str:
        """Pull the answer string out of a RAG-tool result.

        Args:
            result: The tool's ``Ok`` value — a mapping carrying ``"answer"``.

        Returns:
            The ``"answer"`` string, or ``str(result)`` when it has none.
        """
        match result:
            case {"answer": str() as answer}:
                return answer
            case _:
                return str(result)
