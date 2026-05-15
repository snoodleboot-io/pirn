"""``TreeOfThought`` — beam-search-style reasoning with LLM-scored candidates.

Algorithm:
    1. Receive the resolved ``prompt``, ``LLMProvider``, ``k_candidates``, ``beam_width``, and ``depth``.
    2. Validate input types at process time.
    3. Initialise beam with the prompt as the sole path (score 0.0).
    4. For each depth level:
       a. For each live path, generate k_candidates next-thoughts in parallel.
       b. Score each candidate path using the LLM (numeric 1-10; non-numeric = 0).
       c. Keep the top beam_width scoring candidates as the new beam.
    5. Return the best-scoring path as an ``AgentResponse``.


References:
    - Yao et al. (2023) "Tree of Thoughts: Deliberate Problem Solving with Large Language Models"
"""

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
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        k_candidates: Knot | int = 3,
        beam_width: Knot | int = 2,
        depth: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prompt=prompt,
            llm=llm,
            k_candidates=k_candidates,
            beam_width=beam_width,
            depth=depth,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        prompt: str,
        llm: LLMProvider,
        k_candidates: int,
        beam_width: int,
        depth: int,
        **_: Any,
    ) -> AgentResponse:
        """Expand and score reasoning candidates for D depth levels, return the best-path AgentResponse.

        Args:
            prompt: The initial question or problem to reason about.
            llm: LLM provider used for expansion and scoring.
            k_candidates: Number of candidates to generate at each expansion step.
            beam_width: Number of top candidates to retain at each depth level.
            depth: Number of depth levels to explore.

        Returns:
            An AgentResponse whose content is the best-scoring reasoning path.

        Raises:
            TypeError: If prompt is not a string or llm is not an LLMProvider.
            ValueError: If k_candidates, beam_width, or depth are not positive ints.
        """
        if not isinstance(prompt, str):
            raise TypeError(f"TreeOfThought: prompt must be a string, got {type(prompt).__name__}")
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"TreeOfThought: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(k_candidates, int) or k_candidates <= 0:
            raise ValueError(
                f"TreeOfThought: k_candidates must be a positive int, got {k_candidates!r}"
            )
        if not isinstance(beam_width, int) or beam_width <= 0:
            raise ValueError(
                f"TreeOfThought: beam_width must be a positive int, got {beam_width!r}"
            )
        if not isinstance(depth, int) or depth <= 0:
            raise ValueError(f"TreeOfThought: depth must be a positive int, got {depth!r}")
        beam: list[tuple[str, float]] = [(prompt, 0.0)]
        for _i in range(depth):
            candidates: list[tuple[str, float]] = []
            expansion_tasks = [
                self._expand(path, llm, num_candidates=k_candidates) for path, _s in beam
            ]
            expanded_batches = await asyncio.gather(*expansion_tasks)
            for (parent_path, _s), new_thoughts in zip(beam, expanded_batches, strict=False):
                for thought in new_thoughts:
                    combined = f"{parent_path}\n{thought}"
                    candidates.append((combined, 0.0))
            scored = await asyncio.gather(*[self._score(path, llm) for path, _ in candidates])
            beam = sorted(
                zip([p for p, _ in candidates], scored, strict=False),
                key=lambda pair: pair[1],
                reverse=True,
            )[:beam_width]
        best_path = beam[0][0] if beam else prompt
        return AgentResponse(content=best_path)

    async def _expand(self, path: str, llm: LLMProvider, num_candidates: int) -> list[str]:
        messages = [
            {"role": "system", "content": type(self)._expansion_system},
            {"role": "user", "content": path},
        ]
        tasks = [llm.chat(messages=messages) for _ in range(num_candidates)]
        raws = await asyncio.gather(*tasks)
        return [self._extract_text(raw) for raw in raws]

    async def _score(self, path: str, llm: LLMProvider) -> float:
        messages = [
            {"role": "system", "content": type(self)._scoring_system},
            {"role": "user", "content": path},
        ]
        raw = await llm.chat(messages=messages)
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
