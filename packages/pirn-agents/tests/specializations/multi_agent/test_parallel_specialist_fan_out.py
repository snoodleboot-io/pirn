"""Tests for :class:`ParallelSpecialistFanOut`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.parallel_specialist_fan_out import (
    ParallelSpecialistFanOut,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import response_sink

_SPEC_REGISTRY: dict[str, str] = {}


class StubSpecialist(SubTapestry):
    def __init__(self, *, task: Any = "", _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str = "", **_: Any) -> Knot:
        reply = _SPEC_REGISTRY.get(self.config.id, "ok")
        return response_sink(
            AgentResponse(content=f"{reply}:{task}", finish_reason="stop"),
            f"{self.config.id}_reply",
        )


class FailingSpecialist(SubTapestry):
    """A specialist whose inner run raises — used to exercise the failure path."""

    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Knot:
        raise RuntimeError("specialist boom")


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
        with Tapestry() as t:
            ParallelSpecialistFanOut(
                task="tell-time",
                specialists={"a": spec_a, "b": spec_b},
                _config=KnotConfig(id="fan"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        responses = run.outputs["fan"]
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

    async def test_failure_mode_unchanged_when_a_specialist_fails(self) -> None:
        # The Aggregator rewrite gains NO per-specialist error isolation:
        # SubTapestry raises SubTapestryError on ANY inner failure, so the whole
        # knot fails and the surviving sibling's Ok is not surfaced as a partial
        # mapping — byte-identical to the old asyncio.gather failure mode.
        good = _make_spec("A", "spec_ok")
        with Tapestry():
            bad = FailingSpecialist(_config=KnotConfig(id="spec_bad"))
        with Tapestry() as t:
            ParallelSpecialistFanOut(
                task="tell-time",
                specialists={"ok": good, "bad": bad},
                _config=KnotConfig(id="fan"),
            )
        run = await t.run(RunRequest())
        assert not run.succeeded
        assert "fan" not in run.outputs

    async def test_per_specialist_lineage_lives_in_inner_run_not_outputs(self) -> None:
        # Per-specialist lineage never appears in the outer run.outputs — the
        # invocation knots run in a separate inner RunResult. It is reachable via
        # the outer knot's lineage extra['inner_run_id'] plus a history lookup.
        spec_a = _make_spec("A", "spec_a")
        spec_b = _make_spec("B", "spec_b")
        history = InMemoryHistory()
        with Tapestry(history=history) as t:
            ParallelSpecialistFanOut(
                task="tell-time",
                specialists={"a": spec_a, "b": spec_b},
                _config=KnotConfig(id="fan"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        # Outer outputs hold only the aggregated mapping.
        assert set(run.outputs["fan"].keys()) == {"a", "b"}
        assert "invoke_0" not in run.outputs
        assert "fan_out_aggregate" not in run.outputs
        # The per-specialist knots are in the inner run named by inner_run_id.
        fan_row = next(row for row in run.lineage if row.knot_id == "fan")
        inner_run_id = fan_row.extra["inner_run_id"]
        inner_run = await history.get_run(inner_run_id)
        inner_knot_ids = {row.knot_id for row in inner_run.lineage}
        assert {"invoke_0", "invoke_1", "fan_out_aggregate"} <= inner_knot_ids
