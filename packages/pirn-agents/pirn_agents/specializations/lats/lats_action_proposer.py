"""``LatsActionProposer`` — propose candidate next actions from a trajectory.

Algorithm:
    1. Receive ``task`` (str), the current ``trajectory`` (Sequence[str]), and
       ``llm`` (LLMProvider).
    2. Validate types at process time.
    3. Ask the LLM to list candidate next actions, one per ``- `` line.
    4. Parse and return them as a tuple (deduplicated, order-preserving).

References:
    - Zhou et al. (2024) "Language Agent Tree Search" https://arxiv.org/abs/2310.04406
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.specializations.llm_response_text import extract_response_text


class LatsActionProposer(Knot):
    """Propose candidate next actions to expand a search node."""

    def __init__(
        self,
        *,
        task: Knot | str,
        trajectory: Knot | Sequence[str] = (),
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, trajectory=trajectory, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        trajectory: Sequence[str] = (),
        **_: Any,
    ) -> tuple[str, ...]:
        """Propose candidate next actions for the current trajectory.

        Args:
            task: The task being solved.
            llm: Provider used to propose actions.
            trajectory: The actions taken so far.

        Returns:
            A tuple of candidate next-action strings (deduplicated, in order).

        Raises:
            TypeError: If ``task`` is not a string or ``llm`` is not an
                :class:`LLMProvider`.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"LatsActionProposer: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(task, str):
            raise TypeError(f"LatsActionProposer: task must be a string, got {type(task).__name__}")
        taken = " -> ".join(trajectory) if trajectory else "(none yet)"
        system = (
            "You are exploring possible next actions. List a few distinct candidate "
            "next actions, one per line, each prefixed with '- '."
        )
        user = f"Task:\n{task}\n\nActions taken so far: {taken}"
        raw = await llm.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        return self._parse_actions(extract_response_text(raw))

    @staticmethod
    def _parse_actions(text: str) -> tuple[str, ...]:
        actions: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                action = stripped[2:].strip()
                if action and action not in actions:
                    actions.append(action)
        return tuple(actions)
