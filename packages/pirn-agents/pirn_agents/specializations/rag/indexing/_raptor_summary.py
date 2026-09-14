"""``_RaptorSummary`` — summarize one RAPTOR cluster with the LLM.

Internal per-cluster knot of
:class:`~pirn_agents.specializations.rag.indexing._raptor_assembler._RaptorAssembler`.
Each tree level's clusters are independent of one another, so the assembler
runs one ``_RaptorSummary`` per cluster inside a nested run
(:class:`~pirn.nodes.nested_run_knot.NestedRunKnot`) joined by an
:class:`~pirn.nodes.aggregator.Aggregator`: every summary call gets its own
lineage row, ``Result`` and admission, while the assembler keeps its atomic
dedup short-circuit and single final upsert.

Algorithm:
    1. Join the cluster's node texts with a blank line between them.
    2. Render the summary prompt over the joined text.
    3. Send it to the LLM as one user message.
    4. Return the reply's text: the reply itself when it is a string, its
       ``content`` when it is a dict carrying a string ``content``, else
       ``str(reply)``.

Internal API.

References:
    - Sarthi et al., "RAPTOR" (ICLR 2024): https://arxiv.org/abs/2401.18059
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding


class _RaptorSummary(Knot):
    """Summarize one cluster of RAPTOR node texts into a single summary."""

    _summary_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.indexing.raptor_assembler.summary_prompt",
        default=(
            "Summarize the following passages into one concise summary that preserves the "
            "key facts.\n\n{{ joined }}\n\nSummary:"
        ),
    )

    def __init__(
        self,
        *,
        texts: Knot | tuple[str, ...],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(texts=texts, llm=llm, _config=_config, **kwargs)

    async def process(self, texts: tuple[str, ...], llm: LLMProvider, **_: Any) -> str:
        """Summarize ``texts`` with ``llm``.

        Args:
            texts: The cluster's node texts, in tree order.
            llm: The provider producing the summary.

        Returns:
            The summary text.
        """
        return await _RaptorSummary._summarize(llm, texts)

    @staticmethod
    async def _summarize(llm: LLMProvider, texts: tuple[str, ...]) -> str:
        """Summarize a cluster of node texts into one concise summary."""
        joined = "\n\n".join(texts)
        prompt = _RaptorSummary._summary_prompt.render({"joined": joined})
        raw = await llm.chat([{"role": "user", "content": prompt}])
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
