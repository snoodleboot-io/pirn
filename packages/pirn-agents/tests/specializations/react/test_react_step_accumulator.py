"""Unit tests for :class:`ReActStepAccumulator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.react.react_step_accumulator import (
    ReActStepAccumulator,
)
from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.conversation_payload import ConversationPayload


def _msg(content: str) -> AgentMessage:
    return AgentMessage(role="user", content=content)


class TestReActStepAccumulatorProcess(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ReActStepAccumulator:
        with Tapestry():
            return ReActStepAccumulator(
                prior=ConversationPayload(),
                step_output=ConversationPayload(),
                already_terminated=False,
                _config=KnotConfig(id="rsa"),
            )

    async def test_appends_step_output_to_prior(self) -> None:
        knot = self._make()
        prior = ConversationPayload((_msg("a"), _msg("b")), session_id="s1", token_count=7)
        step = ConversationPayload((_msg("c"),))
        result = await knot.process(prior=prior, step_output=step, already_terminated=False)
        assert isinstance(result, ConversationPayload)
        assert len(result.data) == 3
        assert result.data[-1].content == "c"
        # The transcript's frame travels with it: derived from ``prior``, not rebuilt.
        assert result.metadata.session_id == "s1"
        assert result.metadata.token_count == 7

    async def test_short_circuits_when_already_terminated(self) -> None:
        knot = self._make()
        prior = ConversationPayload((_msg("a"), _msg("b")))
        step = ConversationPayload((_msg("c"),))
        result = await knot.process(prior=prior, step_output=step, already_terminated=True)
        assert result is prior

    async def test_empty_prior_and_step(self) -> None:
        knot = self._make()
        result = await knot.process(
            prior=ConversationPayload(), step_output=ConversationPayload(), already_terminated=False
        )
        assert result.data == ()
