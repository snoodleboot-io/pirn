"""Unit tests for :class:`TokenCountKnot`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.context.token_count_knot import TokenCountKnot
from pirn_agents.context.token_counter import TokenCounter
from pirn_agents.types.agent_message import AgentMessage
from tests.context._stubs import StubWordTokenEstimator


def _make_knot() -> TokenCountKnot:
    @knot
    async def _c() -> TokenCounter:
        return TokenCounter(estimator=StubWordTokenEstimator())

    @knot
    async def _m() -> tuple:
        return ()

    with Tapestry():
        counter = _c(_config=KnotConfig(id="c"))
        messages = _m(_config=KnotConfig(id="m"))
        return TokenCountKnot(counter=counter, messages=messages, _config=KnotConfig(id="count"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_counts_messages(self) -> None:
        k = _make_knot()
        counter = TokenCounter(estimator=StubWordTokenEstimator(), per_message_overhead=0)
        messages = (
            AgentMessage(role="user", content="one two"),
            AgentMessage(role="assistant", content="three"),
        )
        assert await k.process(counter=counter, messages=messages) == 3

    async def test_rejects_non_counter(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, "counter"):
            await k.process(counter="nope", messages=())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
