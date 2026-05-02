"""``ReActStepAccumulator`` — append step output, then freeze on stop.

Wires ``ReActStepExecutor`` outputs back into the running message tail
inside a :class:`ReActLoop`. The current step's messages are always
appended (a ``Final Answer:`` message must remain in the transcript so
the response extractor can surface it). The upstream
:class:`ReActTerminationGate` decides whether *subsequent* unrolled
steps should be skipped — when ``already_terminated`` is true, the
accumulator returns the prior messages unchanged so downstream steps
become no-ops.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_message import AgentMessage


class ReActStepAccumulator(Knot):
    """Append step output to the running message tail, or short-circuit."""

    def __init__(
        self,
        *,
        prior: Knot,
        step_output: Knot,
        already_terminated: Knot | bool,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prior=prior,
            step_output=step_output,
            already_terminated=already_terminated,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        prior: tuple[AgentMessage, ...] | list[AgentMessage],
        step_output: tuple[AgentMessage, ...] | list[AgentMessage],
        already_terminated: bool,
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        prior_tuple = tuple(prior)
        if already_terminated:
            return prior_tuple
        return prior_tuple + tuple(step_output)
