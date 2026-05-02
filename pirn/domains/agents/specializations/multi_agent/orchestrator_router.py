"""``OrchestratorRouter`` — pick a specialist by name from an LLM reply.

Inner stage knot used by :class:`OrchestratorAgent`. Renders the
available specialist names into a routing prompt, asks the LLM which
specialist should handle the task, parses the reply, and returns the
chosen specialist name. If the LLM names an unknown specialist, the
first registered specialist is selected as a deterministic fallback.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class OrchestratorRouter(Knot):
    """Asks an :class:`LLMProvider` to choose a specialist name."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: LLMProvider,
        specialist_names: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "OrchestratorRouter: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        names = tuple(specialist_names)
        if not names:
            raise ValueError(
                "OrchestratorRouter: specialist_names must be non-empty"
            )
        for index, name in enumerate(names):
            if not isinstance(name, str) or not name:
                raise ValueError(
                    f"OrchestratorRouter: specialist_names[{index}] must be a "
                    f"non-empty string, got {name!r}"
                )
        self._llm = llm
        self._names = names
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str, **_: Any) -> str:
        if not isinstance(task, str):
            raise TypeError(
                "OrchestratorRouter: task must be a string, "
                f"got {type(task).__name__}"
            )
        prompt = (
            "You are an orchestrator. Choose exactly one specialist to "
            "handle the task. Reply with the specialist name only.\n\n"
            "Available specialists:\n"
            + "\n".join(f"- {name}" for name in self._names)
            + f"\n\nTask: {task}\n\nSpecialist:"
        )
        chat_messages = [{"role": "user", "content": prompt}]
        raw = await self._llm.chat(chat_messages)
        text = self._extract_text(raw).strip()
        for name in self._names:
            if name in text:
                return name
        return self._names[0]

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
