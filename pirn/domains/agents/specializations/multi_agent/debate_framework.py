"""``DebateFramework`` — multi-round debate judged by an LLM.

A :class:`SubTapestry` that runs ``rounds`` of debate between the
provided debaters. Each round, every debater is invoked via its
``process(task=task, **_)`` shape with the topic plus a textual
recap of every prior round's responses. After ``rounds`` rounds, a
judge LLM picks the best response and the pipeline returns it.

Algorithm:
    1. Validate debaters (≥ 2, all :class:`SubTapestry`) and ``rounds`` (> 0).
    2. For each round ``r`` in ``[0, rounds)``:
       a. Render a ``recap`` string of all prior rounds' responses.
       b. Build a framed task embedding the topic, round number, and recap.
       c. Gather all debater coroutines concurrently via :func:`asyncio.gather`.
       d. Normalise each result to an :class:`AgentResponse`.
    3. Build an inner :class:`Tapestry` with :class:`DebateJudge` over the
       final round's responses.
    4. Execute via ``self._run_inner(inner)`` and return the winning response.


References:
    pirn-native — no external references.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.multi_agent.debate_judge import (
    DebateJudge,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry


class DebateFramework(SubTapestry):
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
    ) -> Any:
        """Run the configured number of debate rounds and return the judge-selected winning response.

        Args:
            topic: The debate topic string provided to all debaters each round.

        Returns:
            The AgentResponse selected by the judge as the strongest argument.

        Raises:
            TypeError: If topic is not a string.
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
        history: list[list[AgentResponse]] = []
        latest_round: list[AgentResponse] = []
        for round_index in range(rounds):
            recap = self._render_recap(history)
            framed = (
                f"Topic: {topic}\n\n"
                f"Round {round_index + 1} of {rounds}.\n"
                f"{recap}\n"
                "Make your strongest argument."
            )
            coros = [debater.process(task=framed) for debater in debater_tuple]
            raw_results = await asyncio.gather(*coros)
            latest_round = []
            for raw in raw_results:
                if isinstance(raw, AgentResponse):
                    latest_round.append(raw)
                else:
                    latest_round.append(
                        AgentResponse(
                            content=str(raw),
                            finish_reason="stop",
                        )
                    )
            history.append(latest_round)
        return DebateJudge(
            topic=topic,
            final_round=tuple(latest_round),
            judge_llm=judge_llm,
            _config=KnotConfig(id="judge"),
        )

    @staticmethod
    def _render_recap(history: list[list[AgentResponse]]) -> str:
        if not history:
            return "No prior rounds."
        lines: list[str] = []
        for round_index, round_responses in enumerate(history):
            lines.append(f"Round {round_index + 1}:")
            for debater_index, response in enumerate(round_responses):
                lines.append(f"  debater_{debater_index}: {response.content}")
        return "\n".join(lines)
