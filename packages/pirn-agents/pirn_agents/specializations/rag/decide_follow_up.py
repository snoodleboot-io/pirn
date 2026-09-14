"""``DecideFollowUp`` — ask the LLM whether more evidence is needed."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText


class DecideFollowUp(Knot):
    """Ask the LLM whether more evidence is needed, and for what query."""

    _decide_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.iterative_retriever.decide_prompt",
        default=(
            "You are running iterative retrieval. Given the original question and the "
            "evidence gathered so far, reply with exactly 'DONE' if the evidence is "
            "sufficient, or 'REFINE: <a sharper follow-up search query>' if more is "
            "needed.\n\nOriginal question: {{ original_query }}\n"
            "Last query: {{ current_query }}\n\nEvidence:\n{{ context }}"
        ),
    )

    def __init__(
        self,
        *,
        original_query: Knot | str,
        current_query: Knot | str,
        merged: Knot | Mapping[str, Mapping[str, Any]],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            original_query=original_query,
            current_query=current_query,
            merged=merged,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        original_query: str,
        current_query: str,
        merged: Mapping[str, Mapping[str, Any]],
        llm: LLMProvider,
        **_: Any,
    ) -> str | None:
        """Ask the LLM to refine; return a follow-up query or ``None`` to stop."""
        return await DecideFollowUp.decide(llm, original_query, merged, current_query)

    @staticmethod
    async def decide(
        llm: LLMProvider,
        original_query: str,
        merged: Mapping[str, Mapping[str, Any]],
        current_query: str,
    ) -> str | None:
        """Ask the LLM to refine; return a follow-up query or ``None`` to stop.

        Args:
            llm: The provider making the decision.
            original_query: The question the retrieval serves.
            merged: The deduplicated evidence gathered so far, keyed by id.
            current_query: The query the last round searched with.

        Returns:
            The follow-up query on a ``REFINE:`` reply, otherwise ``None``.
        """
        context = "\n".join(str(doc) for doc in merged.values()) or "(nothing yet)"
        prompt = DecideFollowUp._decide_prompt.render(
            {
                "original_query": original_query,
                "current_query": current_query,
                "context": context,
            }
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        reply = LlmResponseText().extract(raw).strip()
        if reply.upper().startswith("REFINE:"):
            follow_up = reply.split(":", 1)[1].strip()
            return follow_up or None
        return None
