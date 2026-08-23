"""``DebateFramework`` — multi-round debate judged by an LLM.

A :class:`SubTapestry` that runs ``rounds`` of debate between the provided
debaters. Each round every debater is invoked with the topic plus a recap of
every prior round's responses; after the final round a judge LLM picks the best
response and the pipeline returns it.

``rounds`` is a resolved int, so the round loop is *unrolled* into a graph
rather than run inline with ``asyncio.gather``: per round the framework builds a
:class:`DebateRoundFramer` (renders the round's task from prior rounds), one
:class:`SpecialistInvocation` per debater, and an
:class:`~pirn.nodes.aggregator.Aggregator` collecting that round's ordered
responses. The next round's framer takes the prior aggregators as parents, so
the engine schedules each round's debaters concurrently while keeping the rounds
sequential — matching the old gather exactly. See PIR-714.

Failure mode is UNCHANGED. Any debater failure makes the inner ``tapestry.run``
raise :class:`SubTapestryError` for the whole knot, exactly as the old
per-round ``asyncio.gather`` surfaced the first failure. No per-debater error
isolation is gained (that needs a core change — out of scope). Per-debater
lineage lives in the inner ``RunResult`` reachable via
``lineage[].extra['inner_run_id']`` + history, not in the outer ``run.outputs``.

Algorithm:
    1. Validate debaters (≥ 2, all :class:`SubTapestry`) and ``rounds`` (> 0).
    2. For each round ``r`` in ``[0, rounds)``:
       a. Build a :class:`DebateRoundFramer` fed by rounds ``0..r-1``'s
          aggregators.
       b. Build one :class:`SpecialistInvocation` per debater, each receiving
          the framer as its (Knot-valued) task.
       c. Wire the invocations into an :class:`Aggregator` producing the
          round's ordered response list.
    3. Build a :class:`DebateJudge` over the final round's aggregator and return
       it as the inner pipeline's sink.


References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.multi_agent.debate_judge import (
    DebateJudge,
)
from pirn_agents.specializations.multi_agent.debate_round_framer import (
    DebateRoundFramer,
)
from pirn_agents.specializations.multi_agent.specialist_invocation import (
    SpecialistInvocation,
)
from pirn_agents.types.messaging.agent_response import AgentResponse


def _make_round_combine(count: int) -> Any:
    """Build the combine that orders one round's responses by debater index."""

    def combine(**responses: AgentResponse) -> list[AgentResponse]:
        return [responses[f"debater_{index}"] for index in range(count)]

    return combine


class DebateFramework(AgentPipeline):
    """Runs multi-round debate, judged by ``judge_llm``."""

    def __init__(
        self,
        *,
        topic: Knot | str,
        debaters: Knot | Any,
        judge_llm: Knot | LLMProvider,
        rounds: Knot | int = 3,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            topic=topic,
            debaters=debaters,
            judge_llm=judge_llm,
            rounds=rounds,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        topic: str,
        debaters: Any,
        judge_llm: LLMProvider,
        rounds: int = 3,
        **_: Any,
    ) -> Knot:
        """Unroll the debate rounds into a graph and return the judge sink knot.

        Args:
            topic: The debate topic string provided to all debaters each round.

        Returns:
            The :class:`DebateJudge` sink whose output is the winning response.

        Raises:
            ValueError: If fewer than two debaters or non-positive rounds.
            TypeError: If judge_llm is not an LLMProvider, a debater is not a
                SubTapestry, or topic is not a string.
        """
        if not isinstance(judge_llm, LLMProvider):
            raise TypeError(
                f"DebateFramework: judge_llm must be an LLMProvider, got {type(judge_llm).__name__}"
            )
        debater_tuple = tuple(debaters)
        if len(debater_tuple) < 2:
            raise ValueError(
                f"DebateFramework: at least two debaters are required, got {len(debater_tuple)}"
            )
        for index, debater in enumerate(debater_tuple):
            if not isinstance(debater, SubTapestry):
                raise TypeError(
                    f"DebateFramework: debaters[{index}] must be a "
                    f"SubTapestry, got {type(debater).__name__}"
                )
        if not isinstance(rounds, int) or rounds <= 0:
            raise ValueError(f"DebateFramework: rounds must be a positive int, got {rounds!r}")
        if not isinstance(topic, str):
            raise TypeError(f"DebateFramework: topic must be a string, got {type(topic).__name__}")

        round_aggregators: list[Knot] = []
        for round_index in range(rounds):
            framer = DebateRoundFramer(
                topic=topic,
                round_index=round_index,
                rounds=rounds,
                _config=KnotConfig(id=f"debate_frame_r{round_index}"),
                **{f"round_{prior}": round_aggregators[prior] for prior in range(round_index)},
            )
            invocations: dict[str, Knot] = {}
            for debater_index, debater in enumerate(debater_tuple):
                invocations[f"debater_{debater_index}"] = SpecialistInvocation(
                    specialist=debater,
                    task=framer,
                    _config=KnotConfig(id=f"debate_r{round_index}_d{debater_index}"),
                )
            round_aggregators.append(
                Aggregator(
                    combine=_make_round_combine(len(debater_tuple)),
                    _config=KnotConfig(id=f"debate_round_r{round_index}"),
                    **invocations,
                )
            )

        return DebateJudge(
            topic=topic,
            final_round=round_aggregators[-1],
            judge_llm=judge_llm,
            _config=KnotConfig(id="judge"),
        )
