"""``RAGPromptBuilder`` — fold retrieved context into a prompt string.

Takes a free-form query plus a list of retrieved memory entries and
produces a single prompt string ready to feed into an LLM call. The
formatting is deliberately conservative: each retrieved entry is
serialised on its own line as ``[i] key=value`` pairs so the LLM sees
a stable, parseable shape.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RAGPromptBuilder(Knot):
    """Build a context-augmented prompt for a RAG pipeline."""

    def __init__(
        self,
        *,
        query: Knot | str,
        retrieved: Knot,
        _config: KnotConfig,
        instruction: str = (
            "Answer the question using the retrieved context."
        ),
        **kwargs: Any,
    ) -> None:
        if not isinstance(instruction, str) or not instruction:
            raise ValueError(
                "RAGPromptBuilder: instruction must be a non-empty string"
            )
        super().__init__(
            query=query,
            retrieved=retrieved,
            instruction=instruction,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        retrieved: list[Mapping[str, Any]],
        instruction: str,
        **_: Any,
    ) -> str:
        """Combine the query and retrieved context entries into a formatted LLM prompt string.

        Args:
            query: The user query appended after the context block.
            retrieved: The list of retrieved memory entry Mappings to include as context.
            instruction: The instruction line prepended to the context block.

        Returns:
            A fully-formatted prompt string ready for an LLM chat call.

        Raises:
            TypeError: If query is not a string or any retrieved entry is not a Mapping.
        """
        if not isinstance(query, str):
            raise TypeError(
                "RAGPromptBuilder: query must be a string, "
                f"got {type(query).__name__}"
            )
        rendered_hits: list[str] = []
        for index, hit in enumerate(retrieved):
            if not isinstance(hit, Mapping):
                raise TypeError(
                    f"RAGPromptBuilder: retrieved[{index}] must be a Mapping, "
                    f"got {type(hit).__name__}"
                )
            body = ", ".join(f"{k}={v!r}" for k, v in hit.items())
            rendered_hits.append(f"[{index}] {body}")
        if rendered_hits:
            context_block = "\n".join(rendered_hits)
        else:
            context_block = "(no context retrieved)"
        return (
            f"{instruction}\n\n"
            "Context:\n"
            f"{context_block}\n\n"
            f"Question: {query}\n"
            "Answer:"
        )
