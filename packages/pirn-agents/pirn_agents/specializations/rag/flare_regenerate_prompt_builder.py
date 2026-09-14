"""``FlareRegeneratePromptBuilder`` — build the grounded-rewrite prompt.

Internal API. See ``flare_loop.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.prompt.prompt_binding import PromptBinding


class FlareRegeneratePromptBuilder(Knot):
    """Build the prompt asking the LLM to rewrite a sentence grounded in evidence."""

    _regeneration_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.flare_regenerate_prompt_builder.regeneration_prompt",
        default=(
            "Rewrite the tentative sentence so it is fully supported by the evidence. Reply with "
            "only the corrected sentence.\n\nQuestion: {{ query }}\n\n"
            "Tentative sentence: {{ sentence }}\n\n"
            "Evidence:\n{{ context }}"
        ),
    )

    def __init__(
        self,
        *,
        query: str,
        sentence: Knot,
        docs: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(query=query, sentence=sentence, docs=docs, _config=_config, **kwargs)

    async def process(
        self, query: str, sentence: str, docs: list[Mapping[str, Any]], **_: Any
    ) -> str:
        """Render the regeneration prompt from the query, tentative sentence, and evidence.

        Args:
            query: The original question.
            sentence: The tentative sentence to rewrite.
            docs: Retrieved evidence documents.

        Returns:
            The rendered regeneration prompt.
        """
        context = "\n".join(str(doc) for doc in docs) or "(no evidence retrieved)"
        return type(self)._regeneration_prompt.render(
            {"query": query, "sentence": sentence, "context": context}
        )
