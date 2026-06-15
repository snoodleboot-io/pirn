"""Unit tests for :class:`ReActStepAccumulator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.react.react_step_accumulator import (
    ReActStepAccumulator,
)
from pirn_agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


def _msg(content: str) -> AgentMessage:
    return AgentMessage(role="user", content=content)


class TestReActStepAccumulatorProcess(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ReActStepAccumulator:
        with Tapestry():
            return ReActStepAccumulator(
                prior=(),
                step_output=(),
                already_terminated=False,
                _config=KnotConfig(id="rsa"),
            )

    async def test_appends_step_output_to_prior(self) -> None:
        knot = self._make()
        prior = (_msg("a"), _msg("b"))
        step = (_msg("c"),)
        result = await knot.process(prior=prior, step_output=step, already_terminated=False)
        assert len(result) == 3
        assert result[-1].content == "c"

    async def test_short_circuits_when_already_terminated(self) -> None:
        knot = self._make()
        prior = (_msg("a"), _msg("b"))
        step = (_msg("c"),)
        result = await knot.process(prior=prior, step_output=step, already_terminated=True)
        assert len(result) == 2

    async def test_empty_prior_and_step(self) -> None:
        knot = self._make()
        result = await knot.process(prior=[], step_output=[], already_terminated=False)
        assert result == ()
