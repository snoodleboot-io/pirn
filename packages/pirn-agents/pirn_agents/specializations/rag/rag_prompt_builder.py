"""``RAGPromptBuilder`` — fold retrieved context into a prompt string.

Takes a free-form query plus a list of retrieved memory entries and
produces a single prompt string ready to feed into an LLM call. The
formatting is deliberately conservative: each retrieved entry is
serialised on its own line as ``[i] key=value`` pairs so the LLM sees
a stable, parseable shape.

Algorithm:
    1. Receive ``query``, ``retrieved`` (list of Mappings), and
       ``instruction`` strings.
    2. Validate that ``instruction`` is a non-empty string and ``query``
       is a string.
    3. For each entry in ``retrieved``, verify it is a Mapping and render
       it as ``[i] key=value, ...``.
    4. Join rendered hits with newlines to form a ``context_block``, or
       use ``"(no context retrieved)"`` when the list is empty.
    5. Return the concatenated prompt:
       ``{instruction}\\n\\nContext:\\n{context_block}\\n\\nQuestion: {query}\\nAnswer:``.

Math:
    No quantitative computation — assembly is pure string formatting.

References:
    - Prompt formatting conventions from LangChain RAG templates:
      https://python.langchain.com/docs/use_cases/question_answering/
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.prompt.prompt_binding import PromptBinding


class RAGPromptBuilder(Knot):
    """Build a context-augmented prompt for a RAG pipeline."""

    _instruction: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.rag_prompt_builder.instruction",
        default="Answer the question using the retrieved context.",
    )

    _prompt_layout: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.rag_prompt_builder.prompt_layout",
        default=(
            "{{ instruction }}\n\nContext:\n{{ context_block }}\n\nQuestion: {{ query }}\nAnswer:"
        ),
    )

    def __init__(
        self,
        *,
        query: Knot | str,
        retrieved: Knot | list[Any],
        _config: KnotConfig,
        instruction: Knot | str | None = None,
        **kwargs: Any,
    ) -> None:
        """Wire the builder, defaulting ``instruction`` to the bound built-in.

        Args:
            query: The user query, or a knot producing it.
            retrieved: The retrieved memory entries, or a knot producing them.
            _config: The knot configuration.
            instruction: The instruction line prepended to the context block.
                ``None`` (the default) resolves :attr:`_instruction` *here*, at
                construction time, rather than when this signature is evaluated
                at import — so a prompt pack loaded during application start-up
                still takes effect, and no ``PromptBinding`` ever escapes as a
                parameter default where a ``str`` is expected.
            **kwargs: Forwarded to :class:`Knot`.
        """
        super().__init__(
            query=query,
            retrieved=retrieved,
            instruction=(type(self)._instruction.resolve() if instruction is None else instruction),
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
            ValueError: If instruction is empty.
        """
        if not isinstance(instruction, str) or not instruction:
            raise ValueError("RAGPromptBuilder: instruction must be a non-empty string")
        if not isinstance(query, str):
            raise TypeError(f"RAGPromptBuilder: query must be a string, got {type(query).__name__}")
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
        return type(self)._prompt_layout.render(
            {"instruction": instruction, "context_block": context_block, "query": query}
        )
