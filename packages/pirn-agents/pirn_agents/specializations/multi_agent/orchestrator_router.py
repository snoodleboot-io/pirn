"""``OrchestratorRouter`` — pick a specialist by name from an LLM reply.

Inner stage knot used by :class:`OrchestratorAgent`. Renders the
available specialist names into a routing prompt, asks the LLM which
specialist should handle the task, parses the reply, and returns the
chosen specialist name. If the LLM names an unknown specialist, the
first registered specialist is selected as a deterministic fallback.

Algorithm:
    1. Render available specialist names as a bullet list in the prompt.
    2. Call ``llm.chat`` with the routing prompt and extract the reply text.
    3. Scan the reply for the first occurrence of a registered specialist name.
    4. Return that name, or ``specialist_names[0]`` if none match.


References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider


class OrchestratorRouter(Knot):
    """Asks an :class:`LLMProvider` to choose a specialist name."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        specialist_names: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task=task, llm=llm, specialist_names=specialist_names, _config=_config, **kwargs
        )

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        specialist_names: Sequence[str],
        **_: Any,
    ) -> str:
        """Ask the LLM to choose a specialist name for the task and return the chosen name.

        Args:
            task: The natural-language task string used to select a specialist.

        Returns:
            The specialist name chosen by the LLM, or the first registered name on parse failure.

        Raises:
            TypeError: If task is not a string.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"OrchestratorRouter: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        names = tuple(specialist_names)
        if not names:
            raise ValueError("OrchestratorRouter: specialist_names must be non-empty")
        if not isinstance(task, str):
            raise TypeError(f"OrchestratorRouter: task must be a string, got {type(task).__name__}")
        prompt = (
            "You are an orchestrator. Choose exactly one specialist to "
            "handle the task. Reply with the specialist name only.\n\n"
            "Available specialists:\n"
            + "\n".join(f"- {name}" for name in names)
            + f"\n\nTask: {task}\n\nSpecialist:"
        )
        chat_messages = [{"role": "user", "content": prompt}]
        raw = await llm.chat(chat_messages)
        text = self._extract_text(raw).strip()
        for name in names:
            if name in text:
                return name
        return names[0]

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
