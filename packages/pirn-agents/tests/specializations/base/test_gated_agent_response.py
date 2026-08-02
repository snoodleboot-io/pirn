"""Unit tests for :class:`GatedAgentResponse`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.gate.gate import Gate
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry

from pirn_agents.specializations.base.gated_agent_response import GatedAgentResponse
from pirn_agents.types.messaging.agent_response import AgentResponse


class _Flag(Source):
    def __init__(self, *, value: bool, **kwargs: Any) -> None:
        self._value = value
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> bool:
        return self._value


def _passes(value: bool) -> bool:
    return value


class TestGatedAgentResponse(unittest.IsolatedAsyncioTestCase):
    """The join that lets a single-parent Gate control a multi-input knot."""

    async def _run(self, gate_open: bool) -> Any:
        with Tapestry() as t:
            flag = _Flag(value=gate_open, _config=KnotConfig(id="flag"))
            gate = Gate(input=flag, predicate=_passes, _config=KnotConfig(id="gate"))
            GatedAgentResponse(content="hello", gate=gate, _config=KnotConfig(id="resp"))
        return await t.run(RunRequest())

    async def test_passes_content_through_when_the_gate_is_open(self) -> None:
        result = await self._run(gate_open=True)
        assert result.succeeded
        response = result.outputs["resp"]
        assert isinstance(response, AgentResponse)
        assert response.content == "hello"

    async def test_is_skipped_when_the_gate_is_closed(self) -> None:
        """A closed gate must skip this knot — that is how downstream
        conditional work goes unpaid-for."""
        result = await self._run(gate_open=False)
        assert result.succeeded
        assert "resp" not in result.outputs
