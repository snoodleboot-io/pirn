"""``TreeOfThought`` — beam-search-style reasoning with LLM-scored candidates."""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class TreeOfThought(Knot):
    """Generate K candidates, score them, keep top-M, and expand for D depth levels.

    At each depth level:

    1. For each live path, K new next-thoughts are generated in parallel.
    2. Each candidate is scored by the LLM (numeric 1-10 expected; non-numeric
       responses score 0).
    3. The top-M scoring candidates are retained as the new beam.

    After all depth levels the best-scoring path is returned as an
    :class:`AgentResponse`.
    """

    _expansion_system: str = (
        "You are a reasoning assistant. Generate the next reasoning step "
        "that continues the following thought chain."
    )
    _scoring_system: str = (
        "You are a reasoning evaluator. Rate the quality of the following "
        "reasoning step on a scale from 1 to 10. Reply with a single integer only."
    )

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: LLMProvider,
        _config: KnotConfig,
        k_candidates: int = 3,
        beam_width: int = 2,
        depth: int = 3,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "TreeOfThought: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(k_candidates, int) or k_candidates <= 0:
            raise ValueError(
                "TreeOfThought: k_candidates must be a positive int, "
                f"got {k_candidates!r}"
            )
        if not isinstance(beam_width, int) or beam_width <= 0:
            raise ValueError(
                "TreeOfThought: beam_width must be a positive int, "
                f"got {beam_width!r}"
            )
        if not isinstance(depth, int) or depth <= 0:
            raise ValueError(
                "TreeOfThought: depth must be a positive int, "
                f"got {depth!r}"
            )
        self._llm = llm
        self._k = k_candidates
        self._m = beam_width
        self._depth = depth
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> AgentResponse:
        """Expand and score reasoning candidates for D depth levels, return the best-path AgentResponse.

        Args:
            prompt: The initial question or problem to reason about.

        Returns:
            An AgentResponse whose content is the best-scoring reasoning path.

        Raises:
            TypeError: If prompt is not a string.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                "TreeOfThought: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        beam: list[tuple[str, float]] = [(prompt, 0.0)]
        for _ in range(self._depth):
            candidates: list[tuple[str, float]] = []
            expansion_tasks = [
                self._expand(path, self._k) for path, _ in beam
            ]
            expanded_batches = await asyncio.gather(*expansion_tasks)
            for (parent_path, _), new_thoughts in zip(beam, expanded_batches):
                for thought in new_thoughts:
                    combined = f"{parent_path}\n{thought}"
                    candidates.append((combined, 0.0))
            scored = await asyncio.gather(
                *[self._score(path) for path, _ in candidates]
            )
            beam = sorted(
                zip([p for p, _ in candidates], scored),
                key=lambda pair: pair[1],
                reverse=True,
            )[: self._m]
        best_path = beam[0][0] if beam else prompt
        return AgentResponse(content=best_path)

    async def _expand(self, path: str, k: int) -> list[str]:
        messages = [
            {"role": "system", "content": type(self)._expansion_system},
            {"role": "user", "content": path},
        ]
        tasks = [self._llm.chat(messages=messages) for _ in range(k)]
        raws = await asyncio.gather(*tasks)
        return [self._extract_text(raw) for raw in raws]

    async def _score(self, path: str) -> float:
        messages = [
            {"role": "system", "content": type(self)._scoring_system},
            {"role": "user", "content": path},
        ]
        raw = await self._llm.chat(messages=messages)
        text = self._extract_text(raw).strip()
        try:
            return float(text)
        except ValueError:
            return 0.0

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
