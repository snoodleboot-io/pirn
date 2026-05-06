"""``CapabilityRouter`` — select the best-fit agent by capability matching.

A :class:`Knot` that presents a task description alongside a mapping of
agent names to capability descriptions to an LLM and returns the name
of the agent best suited to handle the task.

Algorithm:
    1. Receive the resolved ``task`` string, ``llm`` provider, and
       ``capabilities`` mapping at process time.
    2. Validate input types; raise on bad types or empty capabilities.
    3. Render a routing prompt listing all agent-name → description pairs.
    4. Call ``llm.chat`` with the prompt.
    5. Extract the text label from the raw LLM response.
    6. Return the label if it matches a known agent name exactly.
    7. Fall back to a case-insensitive substring search over known names.
    8. If no match is found, return the first key in ``capabilities``.


References:
    - pirn-native routing pattern; no external algorithm reference.
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
        llm: Knot | LLMProvider,
        capabilities: Knot | Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task=task, llm=llm, capabilities=capabilities, _config=_config, **kwargs
        )

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        capabilities: Mapping[str, str],
        **_: Any,
    ) -> str:
        """Select the agent whose capabilities best match the task description.

        Args:
            task: The task description to match against agent capabilities.
            llm: The LLM provider used to select the best-fit agent.
            capabilities: A non-empty mapping of agent names to descriptions.

        Returns:
            The name of the best-fit agent.

        Raises:
            TypeError: If task is not a string or llm is not an LLMProvider.
            ValueError: If capabilities is empty or contains invalid keys.
        """
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
        if not isinstance(task, str):
            raise TypeError(
                "CapabilityRouter: task must be a string, "
                f"got {type(task).__name__}"
            )
        agent_lines = "\n".join(
            f"- {name}: {desc}"
            for name, desc in capabilities.items()
        )
        prompt = (
            "Select the single best agent for the task below.\n"
            "Reply with the agent name only.\n\n"
            f"Agents:\n{agent_lines}\n\n"
            f"Task: {task}"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        label = self._extract_text(raw).strip()
        if label in capabilities:
            return label
        for name in capabilities:
            if name.lower() in label.lower():
                return name
        return next(iter(capabilities))

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
