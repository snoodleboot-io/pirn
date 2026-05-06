"""Unit tests for :class:`SpecialistFanOutCollector`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.specialist_fan_out_collector import (
    SpecialistFanOutCollector,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


def _resp(content: str) -> AgentResponse:
    return AgentResponse(content=content, finish_reason="stop")


def _make_knot() -> SpecialistFanOutCollector:
    with Tapestry():
        return SpecialistFanOutCollector(
            responses={"a": _resp("x")},
            _config=KnotConfig(id="sfoc"),
        )


class TestSpecialistFanOutCollectorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_passes_through_valid_mapping(self) -> None:
        k = _make_knot()
        responses = {"spec_a": _resp("A"), "spec_b": _resp("B")}
        out = await k.process(responses=responses)
        assert out["spec_a"].content == "A"
        assert out["spec_b"].content == "B"

    async def test_rejects_non_agent_response_value(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(responses={"a": "not-a-response"})  # type: ignore[dict-item]

    async def test_rejects_non_mapping(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(responses="not-a-mapping")  # type: ignore[arg-type]

    async def test_tapestry_run_integration(self) -> None:
        responses = {"spec_a": _resp("A"), "spec_b": _resp("B")}
        with Tapestry() as t:
            SpecialistFanOutCollector(
                responses=responses,
                _config=KnotConfig(id="sfoc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sfoc"]
        assert out["spec_a"].content == "A"
        assert out["spec_b"].content == "B"
