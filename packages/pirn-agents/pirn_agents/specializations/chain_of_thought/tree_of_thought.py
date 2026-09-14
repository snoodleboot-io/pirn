"""``TreeOfThought`` — beam-search-style reasoning with LLM-scored candidates.

Algorithm:
    1. Receive the resolved ``prompt``, ``LLMProvider``, ``k_candidates``, ``beam_width``, and ``depth``.
    2. Validate input types at process time.
    3. Initialise the beam with the prompt as the sole path (score 0.0).
    4. Build ``depth`` chained rounds (``depth`` is a resolved int, so the
       rounds are statically unrolled — no data-dependent termination is
       involved, unlike an agentic loop). Each round:
       a. ``RepeatBeamForExpansion`` flattens the current beam into one
          entry per ``(path, candidate index)`` pair.
       b. ``ExpandOneThought`` is fanned out over that flat list with a
          core :class:`~pirn.nodes.map_markers.Map`, generating one next-thought
          per entry.
       c. A :class:`~pirn.nodes.reduce_.Reduce` combines each thought with its
          parent path into a new candidate.
       d. ``ScoreCandidate`` is fanned out over the candidates with
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
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.map_markers import Map
from pirn.nodes.reduce_ import Reduce

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.chain_of_thought.combine_expansions import CombineExpansions
from pirn_agents.specializations.chain_of_thought.expand_one_thought import ExpandOneThought
from pirn_agents.specializations.chain_of_thought.repeat_beam_for_expansion import (
    RepeatBeamForExpansion,
)
from pirn_agents.specializations.chain_of_thought.score_candidate import ScoreCandidate
from pirn_agents.specializations.chain_of_thought.top_beam import TopBeam
from pirn_agents.specializations.chain_of_thought.tree_of_thought_result import (
    TreeOfThoughtResult,
)


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

        beam_knot: Knot = Parameter(
            "beam_0",
            list[tuple[str, float]],
            default=[(prompt, 0.0)],
            _config=KnotConfig(id="beam_0"),
        )
        for round_index in range(depth):
            beam_knot = TreeOfThought._build_round(
                beam_knot, llm, k_candidates, beam_width, round_index
            )
        return TreeOfThoughtResult(beam=beam_knot, prompt=prompt, _config=KnotConfig(id="result"))

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
        repeated = RepeatBeamForExpansion(
            beam=beam_knot,
            k_candidates=k_candidates,
            _config=KnotConfig(id=f"repeat_{round_index}"),
        )
        expanded = ExpandOneThought(
            parent_path=Map(repeated),
            llm=llm,
            _config=KnotConfig(id=f"expand_{round_index}"),
        )
        candidates = Reduce(
            of=expanded,
            combine=CombineExpansions.combine,
            _config=KnotConfig(id=f"candidates_{round_index}"),
        )
        scored = ScoreCandidate(
            candidate=Map(candidates),
            llm=llm,
            _config=KnotConfig(id=f"score_{round_index}"),
        )
        return Reduce(
            of=scored,
            combine=functools.partial(TopBeam.combine, beam_width=beam_width),
            _config=KnotConfig(id=f"beam_{round_index + 1}"),
        )
