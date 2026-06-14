"""``OutcomeSimulator`` — simulate best/neutral/worst-case outcomes for a proposed action.

Algorithm:
    1. Build a system prompt instructing the LLM to emit exactly three sections:
       ``Best case:``, ``Neutral case:``, ``Worst case:``.
    2. Send the proposed action as the user message.
    3. Parse the LLM response line-by-line, collecting text under each section header.
    4. Return a :class:`SimulationResult` with the three extracted strings.
       Missing sections default to an empty string.


References:
    - Pearl, J., "Causality: Models, Reasoning, and Inference", 2nd ed., Cambridge
      University Press, 2009. (Motivates structured outcome reasoning.)
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.domains.agents.specializations.reflection.simulation_result import SimulationResult


class OutcomeSimulator(Knot):
    """Ask the LLM to simulate the likely outcomes of a proposed action.

    The LLM is prompted to describe best-case, neutral, and worst-case outcomes.
    A lightweight parser extracts the three sections from the response. Each
    section header is expected to be one of ``Best case:``, ``Neutral case:``,
    or ``Worst case:`` (case-insensitive). If a section is missing in the
    response, an empty string is used for that field.
    """

    _simulation_system: str = (
        "You are a strategic advisor. Given the proposed action below, "
        "simulate three plausible outcomes. Use exactly these section headers "
        "on their own lines:\nBest case:\nNeutral case:\nWorst case:\n"
        "Provide a concise description under each header."
    )

    def __init__(
        self,
        *,
        action: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(action=action, llm=llm, _config=_config, **kwargs)

    async def process(self, action: str, llm: LLMProvider, **_: Any) -> SimulationResult:
        """Simulate best/neutral/worst-case outcomes for the proposed action.

        Args:
            action: A description of the proposed action to simulate outcomes for.
            llm: The LLMProvider to use for simulation.

        Returns:
            A SimulationResult with best_case, neutral_case, and worst_case fields.

        Raises:
            TypeError: If action is not a string or llm is not an LLMProvider.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"OutcomeSimulator: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(action, str):
            raise TypeError(
                f"OutcomeSimulator: action must be a string, got {type(action).__name__}"
            )
        messages = [
            {"role": "system", "content": type(self)._simulation_system},
            {"role": "user", "content": action},
        ]
        raw = await llm.chat(messages=messages)
        text = self._extract_text(raw)
        best, neutral, worst = self._parse_outcomes(text)
        return SimulationResult(
            best_case=best,
            neutral_case=neutral,
            worst_case=worst,
        )

    @staticmethod
    def _parse_outcomes(text: str) -> tuple[str, str, str]:
        sections: dict[str, list[str]] = {
            "best": [],
            "neutral": [],
            "worst": [],
        }
        current: str | None = None
        for line in text.splitlines():
            lower = line.strip().lower()
            if lower.startswith("best case"):
                current = "best"
            elif lower.startswith("neutral case"):
                current = "neutral"
            elif lower.startswith("worst case"):
                current = "worst"
            elif current is not None and line.strip():
                sections[current].append(line.strip())
        return (
            " ".join(sections["best"]),
            " ".join(sections["neutral"]),
            " ".join(sections["worst"]),
        )

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
        return str(raw)
