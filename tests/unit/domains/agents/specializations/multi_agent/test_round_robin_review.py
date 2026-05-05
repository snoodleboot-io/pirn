"""Unit tests for :class:`RoundRobinReview`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.round_robin_review import (
    RoundRobinReview,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class _AppendReviewer(SubTapestry):
    """Stub reviewer that appends a suffix to the response content."""

    def __init__(self, suffix: str, *, _config: KnotConfig, **kwargs: Any) -> None:
        self._suffix = suffix
        super().__init__(_config=_config, **kwargs)

    async def process(self, **kwargs: Any) -> AgentResponse:
        response = kwargs.get("response")
        if response is None:
            return AgentResponse(content=self._suffix, finish_reason="stop")
        return AgentResponse(content=response.content + self._suffix, finish_reason="stop")


class TestRoundRobinReviewConstruction(unittest.TestCase):
    def test_rejects_empty_reviewers(self) -> None:
        with self.assertRaisesRegex(ValueError, "reviewers"):
            with Tapestry():
                RoundRobinReview(
                    response=AgentResponse(content="draft", finish_reason="stop"),
                    reviewers=[],
                    _config=KnotConfig(id="rrr"),
                )


class TestRoundRobinReviewProcess(unittest.IsolatedAsyncioTestCase):
    async def test_passes_response_through_each_reviewer(self) -> None:
        response = AgentResponse(content="draft", finish_reason="stop")
        with Tapestry():
            r1 = _AppendReviewer("-r1", _config=KnotConfig(id="r1"))
            r2 = _AppendReviewer("-r2", _config=KnotConfig(id="r2"))
        with Tapestry() as t:
            RoundRobinReview(
                response=response,
                reviewers=[r1, r2],
                _config=KnotConfig(id="rrr"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["rrr"].content == "draft-r1-r2"

    async def test_rejects_non_agent_response(self) -> None:
        with Tapestry():
            r1 = _AppendReviewer("-r1", _config=KnotConfig(id="r1"))
        with Tapestry():
            with self.assertRaises(TypeError):
                RoundRobinReview(
                    response="not-a-response",  # type: ignore[arg-type]
                    reviewers=[r1],
                    _config=KnotConfig(id="rrr"),
                )
