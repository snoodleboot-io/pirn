"""Unit tests for :class:`TerminationGate`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.control.termination_gate import TerminationGate
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


@knot
async def emit_finished() -> AgentResponse:
    return AgentResponse(content="done", finish_reason="stop")


@knot
async def emit_unfinished() -> AgentResponse:
    return AgentResponse(content="thinking", finish_reason="tool_use")


@pytest.mark.asyncio
class TestProcess:
    async def test_terminates_on_stop_finish_reason(self) -> None:
        with Tapestry() as t:
            r = emit_finished(_config=KnotConfig(id="r"))
            TerminationGate(
                response=r,
                max_iterations=5,
                current_iteration=1,
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["g"] is True

    async def test_terminates_at_max_iterations(self) -> None:
        with Tapestry() as t:
            r = emit_unfinished(_config=KnotConfig(id="r"))
            TerminationGate(
                response=r,
                max_iterations=3,
                current_iteration=3,
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["g"] is True

    async def test_continues_when_below_cap_and_unfinished(self) -> None:
        with Tapestry() as t:
            r = emit_unfinished(_config=KnotConfig(id="r"))
            TerminationGate(
                response=r,
                max_iterations=5,
                current_iteration=2,
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["g"] is False


class TestConstruction:
    def test_rejects_zero_max_iterations(self) -> None:
        @knot
        async def r() -> AgentResponse:
            return AgentResponse(content="x")

        with Tapestry():
            rr = r(_config=KnotConfig(id="r"))
            with pytest.raises(ValueError, match="positive"):
                TerminationGate(
                    response=rr,
                    max_iterations=0,
                    current_iteration=0,
                    _config=KnotConfig(id="g"),
                )
