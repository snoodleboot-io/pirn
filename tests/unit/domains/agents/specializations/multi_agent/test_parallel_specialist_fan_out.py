"""Tests for :class:`ParallelSpecialistFanOut`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.parallel_specialist_fan_out import (
    ParallelSpecialistFanOut,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

_SPEC_REGISTRY: dict[str, str] = {}


class StubSpecialist(SubTapestry):
    def __init__(self, *, task: Any = "", _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str = "", **_: Any) -> AgentResponse:
        reply = _SPEC_REGISTRY.get(self.config.id, "ok")
        return AgentResponse(content=f"{reply}:{task}", finish_reason="stop")


def _make_spec(reply: str, id_: str) -> StubSpecialist:
    _SPEC_REGISTRY[id_] = reply
    with Tapestry():
        return StubSpecialist(_config=KnotConfig(id=id_))


def _make_knot(specialists: dict) -> ParallelSpecialistFanOut:
    with Tapestry():
        return ParallelSpecialistFanOut(
            task="t",
            specialists=specialists,
            _config=KnotConfig(id="fan"),
        )


class TestParallelSpecialistFanOutProcess(unittest.IsolatedAsyncioTestCase):
    async def test_collects_responses_from_every_specialist(self) -> None:
        spec_a = _make_spec("A", "spec_a")
        spec_b = _make_spec("B", "spec_b")
        k = _make_knot({"a": spec_a, "b": spec_b})
        responses = await k.process(task="tell-time", specialists={"a": spec_a, "b": spec_b})
        assert set(responses.keys()) == {"a", "b"}
        assert isinstance(responses["a"], AgentResponse)
        assert responses["a"].content == "A:tell-time"
        assert responses["b"].content == "B:tell-time"

    async def test_rejects_empty_specialists(self) -> None:
        spec = _make_spec("x", "s")
        k = _make_knot({"s": spec})
        with self.assertRaises(ValueError):
            await k.process(task="t", specialists={})

    async def test_tapestry_run_integration(self) -> None:
        spec_a = _make_spec("A", "spec_a")
        spec_b = _make_spec("B", "spec_b")
        with Tapestry() as t:
            ParallelSpecialistFanOut(
                task="tell-time",
                specialists={"a": spec_a, "b": spec_b},
                _config=KnotConfig(id="fan"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        responses = result.outputs["fan"]
        assert set(responses.keys()) == {"a", "b"}
        assert responses["a"].content == "A:tell-time"
        assert responses["b"].content == "B:tell-time"
