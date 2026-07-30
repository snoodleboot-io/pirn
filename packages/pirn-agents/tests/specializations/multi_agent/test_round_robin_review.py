"""Unit tests for :class:`RoundRobinReview`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.round_robin_review import (
    RoundRobinReview,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import response_sink

_REVIEWER_REGISTRY: dict[str, str] = {}


class _AppendReviewer(SubTapestry):
    """Stub reviewer that appends a suffix to the response content."""

    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **kwargs: Any) -> Knot:
        suffix = _REVIEWER_REGISTRY.get(self.config.id, "")
        response = kwargs.get("response")
        content = suffix if response is None else response.content + suffix
        return response_sink(
            AgentResponse(content=content, finish_reason="stop"),
            f"{self.config.id}_review",
        )


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
        response = AgentResponse(content="draft", finish_reason="stop")
        with Tapestry() as t:
            RoundRobinReview(
                response=response,
                reviewers=[r1, r2],
                _config=KnotConfig(id="rrr"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["rrr"]
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
