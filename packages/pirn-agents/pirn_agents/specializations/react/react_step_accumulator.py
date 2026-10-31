"""``ReActStepAccumulator`` — append step output, then freeze on stop.

Wires ``ReActStepExecutor`` outputs back into the running message tail
inside a :class:`ReActLoop`. The current step's messages are always
appended (a ``Final Answer:`` message must remain in the transcript so
the response extractor can surface it). The upstream
:class:`ReActTerminationCheck` decides whether *subsequent* unrolled
steps should be skipped — when ``already_terminated`` is true, the
accumulator returns the prior messages unchanged so downstream steps
become no-ops.

Algorithm:
    1. Receive ``prior``, ``step_output``, and ``already_terminated`` at
       process time.
    2. Convert ``prior`` to a tuple.
    3. If ``already_terminated`` is ``True``, return the prior tuple
       unchanged (short-circuit).
    4. Otherwise return ``prior + tuple(step_output)``.


References:
    - Yao et al. (2023) "ReAct: Synergizing Reasoning and Acting in Language Models"
      https://arxiv.org/abs/2210.03629
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.conversation_payload import ConversationPayload


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
        prior: ConversationPayload,
        step_output: ConversationPayload,
        already_terminated: bool,
        **_: Any,
    ) -> ConversationPayload:
        """Append the step's messages to the transcript, or pass it through once terminated.

        Args:
            prior: The transcript accumulated over every previous step.
            step_output: The messages the current step produced.
            already_terminated: Whether a prior step has already signalled termination.

        Returns:
            ``prior`` derived with ``step_output``'s messages appended — the same
            ``ConversationFrame`` (session, turn, token count) carried forward —
            or ``prior`` itself when the loop has already terminated (ADR
            agents-speaks-core WS6b; PIR-874).
        """
        if already_terminated:
            return prior
        return prior.derive((*prior.data, *step_output.data))
