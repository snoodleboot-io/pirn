"""``DebateRoundFramer`` — build one debate round's framed task at runtime.

Inner stage knot used by :class:`DebateFramework`. The framed prompt for round
``r`` embeds a recap of *every prior round's responses*, so it cannot be
rendered when the graph is built — the prior rounds have not run yet. This knot
takes the prior rounds' aggregated response lists as parents and produces the
framed task string the round's debaters receive.

Round 0 has no prior rounds, so its recap is ``"No prior rounds."`` and the
knot's only parents are the coerced ``topic`` / ``round_index`` / ``rounds``
scalars.

The framing string is byte-for-byte identical to the one the old
``DebateFramework`` built inline inside its ``asyncio.gather`` loop, so debater
inputs are unchanged. See PIR-714.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_response import AgentResponse


class DebateRoundFramer(Knot):
    """Render the framed task for a single debate round."""

    def __init__(
        self,
        *,
        topic: Knot | str,
        round_index: Knot | int,
        rounds: Knot | int,
        _config: KnotConfig,
        **prior_rounds: Knot,
    ) -> None:
        # ``prior_rounds`` are keyed ``round_0``, ``round_1``, … — one parent per
        # prior round, each resolving to that round's ordered list of responses.
        super().__init__(
            topic=topic,
            round_index=round_index,
            rounds=rounds,
            _config=_config,
            **prior_rounds,
        )

    async def process(
        self,
        topic: str,
        round_index: int,
        rounds: int,
        **prior_rounds: Sequence[AgentResponse],
    ) -> str:
        """Render the framed task string for round ``round_index``.

        Args:
            topic: The debate topic.
            round_index: Zero-based index of the round being framed.
            rounds: Total number of rounds (for the ``Round X of N`` line).
            **prior_rounds: Prior rounds' response lists, keyed ``round_<i>``.

        Returns:
            The framed task string handed to every debater this round.
        """
        history = [list(prior_rounds[f"round_{index}"]) for index in range(round_index)]
        recap = self._render_recap(history)
        return (
            f"Topic: {topic}\n\n"
            f"Round {round_index + 1} of {rounds}.\n"
            f"{recap}\n"
            "Make your strongest argument."
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
