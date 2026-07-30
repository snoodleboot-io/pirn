"""``_SummaryReducer`` — combine per-chunk summaries into one.

The reduce half of the map-reduce summariser, split out of
``_MapReduceSummariser``.

**Why a named ``Knot`` and not core's ``Reduce``.** Two independent blockers,
both structural:

* ``Reduce.__init__`` takes only ``of: Knot``, so ``llm`` cannot be wired as a
  parent — and the reduce step here *is* an LLM call.
* WS6's prompt-pin harness builds a bare instance via ``_bare(cls)`` and reads
  the ``ClassVar[PromptBinding]`` off the class. A ``Reduce(combine=<fn>)``
  carries no such class, so the reduce prompt would drop out of pin coverage.

The second is the binding one and does not go away: PIR-768 fixed ``Reduce``
invoking an async ``combine`` without awaiting, and that changes nothing here.

The reduce is a **hard barrier**, not a pairwise fold — folding would turn one
LLM call into N-1 and change the output.

Note:
    The ``PromptBinding`` name still reads ``_map_reduce_summariser.*`` even
    though that module is gone. Deliberate: the binding name is an
    **operator-facing override key**, and renaming it would silently break any
    deployment overriding this prompt.

Internal API.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding


class _SummaryReducer(Knot):
    """Reduce N per-chunk summaries to one, short-circuiting the degenerate cases."""

    _reduce_system: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.document_processing._map_reduce_summariser.reduce_system",
        default=(
            "Combine the following per-chunk summaries into one "
            "coherent summary of the entire document. Avoid "
            "repetition and preserve chronological order."
        ),
    )

    def __init__(
        self,
        *,
        summaries: Knot,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(summaries=summaries, llm=llm, _config=_config, **kwargs)

    async def process(self, summaries: list[str], llm: LLMProvider, **_: Any) -> str:
        """Combine ``summaries`` into a single summary.

        Both degenerate cases are absorbed here, as they were in the class this
        replaced: no chunks yields the empty string, and a single chunk passes
        its summary through without a second LLM call.

        Args:
            summaries: Per-chunk summaries in document order.
            llm: The provider to call for the combining step.

        Returns:
            The combined summary, or the sole summary, or ``""``.
        """
        if not summaries:
            return ""
        if len(summaries) == 1:
            return summaries[0]
        joined = "\n\n".join(f"Summary {i + 1}: {s}" for i, s in enumerate(summaries))
        chat_messages = [
            {
                "role": "system",
                "content": type(self)._reduce_system.resolve(),
            },
            {"role": "user", "content": joined},
        ]
        raw = await llm.chat(chat_messages)
        return _SummaryReducer._extract_text(raw)

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text
                if isinstance(first, str):
                    return first
            text = raw.get("text")
            if isinstance(text, str):
                return text
        return str(raw)
