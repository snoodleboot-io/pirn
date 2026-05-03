"""``DebateFramework`` — multi-round debate judged by an LLM.

A :class:`SubTapestry` that runs ``rounds`` of debate between the
provided debaters. Each round, every debater is invoked via its
``process(task=task, **_)`` shape with the topic plus a textual
recap of every prior round's responses. After ``rounds`` rounds, a
judge LLM picks the best response and the pipeline returns it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.multi_agent.debate_judge import (
    DebateJudge,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class DebateFramework(SubTapestry):
    """Runs multi-round debate, judged by ``judge_llm``."""

    def __init__(
        self,
        *,
        topic: Knot | str,
        debaters: Sequence[SubTapestry],
        judge_llm: LLMProvider,
        _config: KnotConfig,
        rounds: int = 3,
        **kwargs: Any,
    ) -> None:
        debater_tuple = tuple(debaters)
        if len(debater_tuple) < 2:
            raise ValueError(
                "DebateFramework: at least two debaters are required, "
                f"got {len(debater_tuple)}"
            )
        for index, debater in enumerate(debater_tuple):
            if not isinstance(debater, SubTapestry):
                raise TypeError(
                    f"DebateFramework: debaters[{index}] must be a "
                    f"SubTapestry, got {type(debater).__name__}"
                )
        if not isinstance(judge_llm, LLMProvider):
            raise TypeError(
                "DebateFramework: judge_llm must be an LLMProvider, "
                f"got {type(judge_llm).__name__}"
            )
        if not isinstance(rounds, int) or rounds <= 0:
            raise ValueError(
                "DebateFramework: rounds must be a positive int, "
                f"got {rounds!r}"
            )
        self._debaters = debater_tuple
        self._judge_llm = judge_llm
        self._rounds = rounds
        super().__init__(topic=topic, _config=_config, **kwargs)

    async def process(self, topic: str, **_: Any) -> AgentResponse:
        """Run the configured number of debate rounds and return the judge-selected winning response.

        Args:
            topic: The debate topic string provided to all debaters each round.

        Returns:
            The AgentResponse selected by the judge as the strongest argument.

        Raises:
            TypeError: If topic is not a string.
        """
        if not isinstance(topic, str):
            raise TypeError(
                "DebateFramework: topic must be a string, "
                f"got {type(topic).__name__}"
            )
        history: list[list[AgentResponse]] = []
        latest_round: list[AgentResponse] = []
        for round_index in range(self._rounds):
            recap = self._render_recap(history)
            framed = (
                f"Topic: {topic}\n\n"
                f"Round {round_index + 1} of {self._rounds}.\n"
                f"{recap}\n"
                "Make your strongest argument."
            )
            coros = [debater.process(task=framed) for debater in self._debaters]
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
        with Tapestry() as inner:
            DebateJudge(
                topic=topic,
                final_round=tuple(latest_round),
                judge_llm=self._judge_llm,
                _config=KnotConfig(id="judge"),
            )
        inner_result = await self._run_inner(inner)
        winner = inner_result.outputs.get("judge")
        if not isinstance(winner, AgentResponse):
            return latest_round[0] if latest_round else AgentResponse(
                content="", finish_reason="stop"
            )
        return winner

    @staticmethod
    def _render_recap(history: list[list[AgentResponse]]) -> str:
        if not history:
            return "No prior rounds."
        lines: list[str] = []
        for round_index, round_responses in enumerate(history):
            lines.append(f"Round {round_index + 1}:")
            for debater_index, response in enumerate(round_responses):
                lines.append(
                    f"  debater_{debater_index}: {response.content}"
                )
        return "\n".join(lines)
