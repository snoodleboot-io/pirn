"""Unit tests for :class:`RoundRobinReview`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.round_robin_review import (
    RoundRobinReview,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

_REVIEWER_REGISTRY: dict[str, str] = {}


class _AppendReviewer(SubTapestry):
    """Stub reviewer that appends a suffix to the response content."""

    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **kwargs: Any) -> AgentResponse:
        suffix = _REVIEWER_REGISTRY.get(self.config.id, "")
        response = kwargs.get("response")
        if response is None:
            return AgentResponse(content=suffix, finish_reason="stop")
        return AgentResponse(content=response.content + suffix, finish_reason="stop")


def _make_reviewer(suffix: str, id_: str) -> _AppendReviewer:
    _REVIEWER_REGISTRY[id_] = suffix
    with Tapestry():
        return _AppendReviewer(_config=KnotConfig(id=id_))


def _make_knot(reviewers: list) -> RoundRobinReview:
    with Tapestry():
        return RoundRobinReview(
            response=AgentResponse(content="draft", finish_reason="stop"),
            reviewers=reviewers,
            _config=KnotConfig(id="rrr"),
        )


class TestRoundRobinReviewProcess(unittest.IsolatedAsyncioTestCase):
    async def test_passes_response_through_each_reviewer(self) -> None:
        r1 = _make_reviewer("-r1", "r1")
        r2 = _make_reviewer("-r2", "r2")
        k = _make_knot([r1, r2])
        response = AgentResponse(content="draft", finish_reason="stop")
        result = await k.process(response=response, reviewers=[r1, r2])
        assert result.content == "draft-r1-r2"

    async def test_rejects_non_agent_response(self) -> None:
        r1 = _make_reviewer("-r1", "r1")
        k = _make_knot([r1])
        with self.assertRaises(TypeError):
            await k.process(response="not-a-response", reviewers=[r1])  # type: ignore[arg-type]

    async def test_rejects_empty_reviewers(self) -> None:
        r1 = _make_reviewer("-r1", "r1")
        k = _make_knot([r1])
        response = AgentResponse(content="draft", finish_reason="stop")
        with self.assertRaises(ValueError):
            await k.process(response=response, reviewers=[])

    async def test_tapestry_run_integration(self) -> None:
        r1 = _make_reviewer("-r1", "r1")
        r2 = _make_reviewer("-r2", "r2")
        response = AgentResponse(content="draft", finish_reason="stop")
        with Tapestry() as t:
            RoundRobinReview(
                response=response,
                reviewers=[r1, r2],
                _config=KnotConfig(id="rrr"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["rrr"].content == "draft-r1-r2"
