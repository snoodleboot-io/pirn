"""Tests for :class:`ParallelSpecialistFanOut`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.parallel_specialist_fan_out import (
    ParallelSpecialistFanOut,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class StubSpecialist(SubTapestry):
    def __init__(
        self,
        *,
        task: Any = "",
        _config: KnotConfig,
        reply: str = "ok",
        **kwargs: Any,
    ) -> None:
        self._reply = reply
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str, **_: Any) -> AgentResponse:
        return AgentResponse(
            content=f"{self._reply}:{task}",
            finish_reason="stop",
        )


@pytest.mark.asyncio
class TestParallelSpecialistFanOutConstruction:
    async def test_rejects_empty_specialists(self) -> None:
        with pytest.raises(ValueError, match="specialists"):
            with Tapestry():
                ParallelSpecialistFanOut(
                    task="t",
                    specialists={},
                    _config=KnotConfig(id="fan"),
                )

    async def test_rejects_non_subtapestry_specialist(self) -> None:
        with pytest.raises(TypeError, match="must be a SubTapestry"):
            with Tapestry():
                ParallelSpecialistFanOut(
                    task="t",
                    specialists={"a": "not-a-subtap"},  # type: ignore[dict-item]
                    _config=KnotConfig(id="fan"),
                )


@pytest.mark.asyncio
class TestParallelSpecialistFanOutHappyPath:
    async def test_collects_responses_from_every_specialist(self) -> None:
        with Tapestry():
            spec_a = StubSpecialist(
                _config=KnotConfig(id="spec_a"),
                reply="A",
            )
            spec_b = StubSpecialist(
                _config=KnotConfig(id="spec_b"),
                reply="B",
            )
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
        assert isinstance(responses["a"], AgentResponse)
        assert responses["a"].content == "A:tell-time"
        assert responses["b"].content == "B:tell-time"
