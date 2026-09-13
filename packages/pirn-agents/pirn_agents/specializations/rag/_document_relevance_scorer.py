"""``_DocumentRelevanceScorer`` — score one document's relevance via the LLM."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText


class _DocumentRelevanceScorer(Knot):
    """Score one document's relevance to the query via the LLM.

    Algorithm:
        1. Render the score prompt from ``query`` and the document's text.
        2. Call the LLM and extract plain text from its response.
        3. Parse the reply as a float; default to 0.0 on parse error so a
           malformed reply drops the document to the bottom of the ranking
           instead of failing the whole rerank.

    Math:
        Relevance score :math:`s \\in [0.0, 1.0]` for one document, as judged
        by the LLM from its free-text reply.
    """

    _score_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.reranker.score_prompt",
        default=(
            "Score the relevance of the following document to the query "
            "on a scale from 0.0 (not relevant) to 1.0 (highly relevant). "
            "Reply with only the numeric score.\n\n"
            "Query: {{ query }}\n\nDocument: {{ text }}"
        ),
    )

    def __init__(
        self,
        *,
        query: Knot | str,
        document: Knot | Mapping[str, Any],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(query=query, document=document, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        query: str,
        document: Mapping[str, Any],
        llm: LLMProvider,
        **_: Any,
    ) -> tuple[float, Mapping[str, Any]]:
        """Score ``document``'s relevance to ``query``.

        Args:
            query: The relevance reference query.
            document: The document mapping to score.
            llm: The provider asked to score relevance.

        Returns:
            A ``(score, document)`` pair, ``score`` defaulting to 0.0 when the
            LLM's reply does not parse as a float.
        """
        text = _DocumentRelevanceScorer._doc_text(document)
        prompt = _DocumentRelevanceScorer._score_prompt.render({"query": query, "text": text})
        raw = await llm.chat([{"role": "user", "content": prompt}])
        score_text = LlmResponseText().extract(raw).strip()
        try:
            score = float(score_text)
        except ValueError:
            score = 0.0
        return score, document

    @staticmethod
    def _doc_text(doc: Mapping[str, Any]) -> str:
        parts: list[str] = []
        for value in doc.values():
            parts.append(value if isinstance(value, str) else str(value))
        return " ".join(parts)
