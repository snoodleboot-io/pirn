"""Unit tests for :class:`ReActStepAccumulator`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.react.react_step_accumulator import (
    ReActStepAccumulator,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


def _msg(content: str) -> AgentMessage:
    return AgentMessage(role="user", content=content)


class TestReActStepAccumulatorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_step_output_to_prior(self) -> None:
        prior = (_msg("a"), _msg("b"))
        step = (_msg("c"),)
        with Tapestry() as t:
            ReActStepAccumulator(
                prior=prior,
                step_output=step,
                already_terminated=False,
                _config=KnotConfig(id="rsa"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["rsa"]
        assert len(out) == 3
        assert out[-1].content == "c"

    async def test_short_circuits_when_already_terminated(self) -> None:
        prior = (_msg("a"), _msg("b"))
        step = (_msg("c"),)
        with Tapestry() as t:
            ReActStepAccumulator(
                prior=prior,
                step_output=step,
                already_terminated=True,
                _config=KnotConfig(id="rsa"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["rsa"]
        assert len(out) == 2  # step_output not appended

    async def test_empty_prior_and_step(self) -> None:
        with Tapestry() as t:
            ReActStepAccumulator(
                prior=[],
                step_output=[],
                already_terminated=False,
                _config=KnotConfig(id="rsa"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["rsa"] == ()
