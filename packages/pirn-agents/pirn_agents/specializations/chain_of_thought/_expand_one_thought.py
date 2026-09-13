"""``_ExpandOneThought`` — ask the LLM for the next reasoning step."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText


class _ExpandOneThought(Knot):
    """Ask the LLM for the next reasoning step continuing one parent path."""

    _expansion_system: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.chain_of_thought.tree_of_thought.expansion_system",
        default=(
            "You are a reasoning assistant. Generate the next reasoning step "
            "that continues the following thought chain."
        ),
    )

    def __init__(
        self,
        *,
        parent_path: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent_path=parent_path, llm=llm, _config=_config, **kwargs)

    async def process(self, parent_path: str, llm: LLMProvider, **_: Any) -> tuple[str, str]:
        """Generate one next-thought continuing ``parent_path``.

        Args:
            parent_path: The reasoning path so far.
            llm: The provider generating the next step.

        Returns:
            A ``(parent_path, thought)`` pair.
        """
        messages = [
            {"role": "system", "content": _ExpandOneThought._expansion_system.resolve()},
            {"role": "user", "content": parent_path},
        ]
        raw = await llm.chat(messages=messages)
        return parent_path, LlmResponseText().extract(raw)
