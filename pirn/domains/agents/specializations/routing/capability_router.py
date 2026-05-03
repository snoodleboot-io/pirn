"""``CapabilityRouter`` — select the best-fit agent by capability matching.

A :class:`Knot` that presents a task description alongside a mapping of
agent names to capability descriptions to an LLM and returns the name
of the agent best suited to handle the task.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class CapabilityRouter(Knot):
    """Use LLM to select the best-fit agent from a capability description map."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: LLMProvider,
        capabilities: Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "CapabilityRouter: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(capabilities, Mapping) or not capabilities:
            raise ValueError(
                "CapabilityRouter: capabilities must be a non-empty mapping"
            )
        for name, desc in capabilities.items():
            if not isinstance(name, str) or not name:
                raise ValueError(
                    f"CapabilityRouter: capabilities key must be a non-empty "
                    f"string, got {name!r}"
                )
            if not isinstance(desc, str):
                raise TypeError(
                    f"CapabilityRouter: capabilities[{name!r}] must be a "
                    f"string, got {type(desc).__name__}"
                )
        self._llm = llm
        self._capabilities: dict[str, str] = dict(capabilities)
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(
        self,
        task: str,
        **_: Any,
    ) -> str:
        """Select the agent whose capabilities best match the task description.

        Args:
            task: The task description to match against agent capabilities.

        Returns:
            The name of the best-fit agent.

        Raises:
            TypeError: If task is not a string.
        """
        if not isinstance(task, str):
            raise TypeError(
                "CapabilityRouter: task must be a string, "
                f"got {type(task).__name__}"
            )
        agent_lines = "\n".join(
            f"- {name}: {desc}"
            for name, desc in self._capabilities.items()
        )
        prompt = (
            "Select the single best agent for the task below.\n"
            "Reply with the agent name only.\n\n"
            f"Agents:\n{agent_lines}\n\n"
            f"Task: {task}"
        )
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
        label = self._extract_text(raw).strip()
        if label in self._capabilities:
            return label
        for name in self._capabilities:
            if name.lower() in label.lower():
                return name
        return next(iter(self._capabilities))

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
