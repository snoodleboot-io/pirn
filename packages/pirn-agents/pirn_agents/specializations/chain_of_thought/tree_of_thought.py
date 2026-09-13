"""``TreeOfThought`` — beam-search-style reasoning with LLM-scored candidates.

Algorithm:
    1. Receive the resolved ``prompt``, ``LLMProvider``, ``k_candidates``, ``beam_width``, and ``depth``.
    2. Validate input types at process time.
    3. Initialise the beam with the prompt as the sole path (score 0.0).
    4. Build ``depth`` chained rounds (``depth`` is a resolved int, so the
       rounds are statically unrolled — no data-dependent termination is
       involved, unlike an agentic loop). Each round:
       a. :class:`_RepeatBeamForExpansion` flattens the current beam into one
          entry per ``(path, candidate index)`` pair.
       b. :class:`_ExpandOneThought` is fanned out over that flat list with a
          core :class:`~pirn.nodes.map_markers.Map`, generating one next-thought
          per entry.
       c. A :class:`~pirn.nodes.reduce_.Reduce` combines each thought with its
          parent path into a new candidate.
       d. :class:`_ScoreCandidate` is fanned out over the candidates with
          another ``Map``, scoring each (numeric 1-10 expected; non-numeric
          responses score 0).
       e. A :class:`~pirn.nodes.reduce_.Reduce` sorts by score and keeps the
          top ``beam_width`` candidates as the next round's beam.
    5. Return the best-scoring path as an ``AgentResponse``.

Every LLM call — expansion and scoring alike — is its own engine-scheduled
:class:`~pirn.nodes.map_markers.Map` invocation rather than a hand-rolled
``asyncio.gather``, so each gets its own ``Result``, history record, and
lineage, and the engine (not a local gather) schedules the concurrency
(PIR-841).

References:
    - Yao et al. (2023) "Tree of Thoughts: Deliberate Problem Solving with Large Language Models"
"""

from __future__ import annotations

import functools
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.map_markers import Map
from pirn.nodes.reduce_ import Reduce

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.resolved_value_knot import ResolvedValueKnot
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.types.messaging.agent_response import AgentResponse


class _RepeatBeamForExpansion(Knot):
    """Flatten the beam into one entry per ``(path, candidate index)`` pair."""

    def __init__(
        self,
        *,
        beam: Knot | list[tuple[str, float]],
        k_candidates: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(beam=beam, k_candidates=k_candidates, _config=_config, **kwargs)

    async def process(
        self, beam: list[tuple[str, float]], k_candidates: int, **_: Any
    ) -> list[str]:
        """Repeat each beam path ``k_candidates`` times, flattened.

        Args:
            beam: The current beam, as ``(path, score)`` pairs.
            k_candidates: Number of next-thoughts to request per path.

        Returns:
            A flat list of parent paths, each repeated ``k_candidates`` times.
        """
        return [path for path, _score in beam for _ in range(k_candidates)]


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


class _CombineExpansions:
    """Reduce ``combine`` target: fold each thought into a new candidate path."""

    @staticmethod
    def combine(items: list[tuple[str, str]]) -> list[tuple[str, float]]:
        """Join each ``(parent_path, thought)`` pair into a scored-0.0 candidate."""
        return [(f"{parent_path}\n{thought}", 0.0) for parent_path, thought in items]


class _ScoreCandidate(Knot):
    """Ask the LLM to rate one candidate reasoning path."""

    _scoring_system: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.chain_of_thought.tree_of_thought.scoring_system",
        default=(
            "You are a reasoning evaluator. Rate the quality of the following "
            "reasoning step on a scale from 1 to 10. Reply with a single integer only."
        ),
    )

    def __init__(
        self,
        *,
        candidate: Knot | tuple[str, float],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(candidate=candidate, llm=llm, _config=_config, **kwargs)

    async def process(
        self, candidate: tuple[str, float], llm: LLMProvider, **_: Any
    ) -> tuple[str, float]:
        """Score ``candidate``'s path.

        Args:
            candidate: The ``(path, placeholder_score)`` pair to score.
            llm: The provider used to rate the path.

        Returns:
            A ``(path, score)`` pair; ``score`` defaults to 0.0 when the LLM's
            reply does not parse as a float.

        Math:
            Score :math:`s \\in \\{0\\} \\cup [1, 10]` as judged by the LLM;
            0 when its reply does not parse as a number.
        """
        path, _placeholder = candidate
        messages = [
            {"role": "system", "content": _ScoreCandidate._scoring_system.resolve()},
            {"role": "user", "content": path},
        ]
        raw = await llm.chat(messages=messages)
        text = LlmResponseText().extract(raw).strip()
        try:
            return path, float(text)
        except ValueError:
            return path, 0.0


class _TopBeam:
    """Reduce ``combine`` target: keep the top-``beam_width`` scoring candidates."""

    @staticmethod
    def combine(items: list[tuple[str, float]], *, beam_width: int) -> list[tuple[str, float]]:
        """Sort ``items`` by descending score and keep the top ``beam_width``."""
        return sorted(items, key=lambda pair: pair[1], reverse=True)[:beam_width]


class _TreeOfThoughtResult(Knot):
    """Extract the best-scoring path from the final beam."""

    def __init__(
        self,
        *,
        beam: Knot | list[tuple[str, float]],
        prompt: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(beam=beam, prompt=prompt, _config=_config, **kwargs)

    async def process(self, beam: list[tuple[str, float]], prompt: str, **_: Any) -> AgentResponse:
        """Return the top beam entry's path as an :class:`AgentResponse`."""
        best_path = beam[0][0] if beam else prompt
        return AgentResponse(content=best_path)


class TreeOfThought(AgentPipeline):
    """Generate K candidates, score them, keep top-M, and expand for D depth levels.

    At each depth level:

    1. For each live path, K new next-thoughts are generated in parallel.
    2. Each candidate is scored by the LLM (numeric 1-10 expected; non-numeric
       responses score 0).
    3. The top-M scoring candidates are retained as the new beam.

    After all depth levels the best-scoring path is returned as an
    :class:`AgentResponse`.
    """

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
    ) -> Knot:
        """Build the depth-round expand/score chain and return the result sink knot.

        Args:
            prompt: The initial question or problem to reason about.
            llm: LLM provider used for expansion and scoring.
            k_candidates: Number of candidates to generate at each expansion step.
            beam_width: Number of top candidates to retain at each depth level.
            depth: Number of depth levels to explore.

        Returns:
            The sink knot whose output is an :class:`AgentResponse` carrying
            the best-scoring reasoning path.

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

        beam_knot: Knot = ResolvedValueKnot(value=[(prompt, 0.0)], _config=KnotConfig(id="beam_0"))
        for round_index in range(depth):
            beam_knot = TreeOfThought._build_round(
                beam_knot, llm, k_candidates, beam_width, round_index
            )
        return _TreeOfThoughtResult(beam=beam_knot, prompt=prompt, _config=KnotConfig(id="result"))

    @staticmethod
    def _build_round(
        beam_knot: Knot,
        llm: LLMProvider,
        k_candidates: int,
        beam_width: int,
        round_index: int,
    ) -> Knot:
        """Build one expand-then-score round and return the new beam knot.

        Args:
            beam_knot: The knot producing the current beam.
            llm: The provider used for expansion and scoring.
            k_candidates: Number of candidates to generate per live path.
            beam_width: Number of top candidates to retain.
            round_index: This round's 0-based depth index, for unique knot ids.

        Returns:
            The :class:`~pirn.nodes.reduce_.Reduce` knot producing the next beam.
        """
        repeated = _RepeatBeamForExpansion(
            beam=beam_knot,
            k_candidates=k_candidates,
            _config=KnotConfig(id=f"repeat_{round_index}"),
        )
        expanded = _ExpandOneThought(
            # Core's Map marker is consumed at construction by
            # `knot.py:199-205` and is deliberately not a Knot, so it does not
            # satisfy the declared `Knot | str`. Inline suppression is the
            # house idiom for this; see PIR-715/PIR-716.
            parent_path=Map(repeated),  # pyright: ignore[reportArgumentType]
            llm=llm,
            _config=KnotConfig(id=f"expand_{round_index}"),
        )
        candidates = Reduce(
            of=expanded,
            combine=_CombineExpansions.combine,
            _config=KnotConfig(id=f"candidates_{round_index}"),
        )
        scored = _ScoreCandidate(
            candidate=Map(candidates),  # pyright: ignore[reportArgumentType]
            llm=llm,
            _config=KnotConfig(id=f"score_{round_index}"),
        )
        return Reduce(
            of=scored,
            combine=functools.partial(_TopBeam.combine, beam_width=beam_width),
            _config=KnotConfig(id=f"beam_{round_index + 1}"),
        )
