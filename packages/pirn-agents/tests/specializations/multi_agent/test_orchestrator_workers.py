"""Tests for :class:`OrchestratorWorkers` (S6, dynamic fan-out via F7)."""

from __future__ import annotations

import asyncio
import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.agent_tool import AgentTool
from pirn_agents.specializations.multi_agent.orchestrator_workers import OrchestratorWorkers
from pirn_agents.specializations.multi_agent.orchestrator_workers_result import (
    OrchestratorWorkersResult,
)
from pirn_agents.tool import Tool
from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.types.tool_status import ToolStatus
from tests.agent_tool_doubles import StubAgent, reset_doubles
from tests.specializations.conftest import StubTool


class _ConcurrencyProbeTool(Tool):
    """Records the peak number of simultaneously in-flight invocations."""

    def __init__(self) -> None:
        self._current = 0
        self.peak = 0

    @property
    def name(self) -> str:
        return "probe"

    @property
    def description(self) -> str:
        return "probe"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {"task": {"type": "string"}}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        self._current += 1
        self.peak = max(self.peak, self._current)
        await asyncio.sleep(0.01)
        self._current -= 1
        return f"done:{arguments['task']}"


def _echo(arguments: Mapping[str, Any]) -> Any:
    if arguments["task"] == "bad":
        raise RuntimeError("worker failed")
    return f"done:{arguments['task']}"


class TestOrchestratorWorkers(unittest.IsolatedAsyncioTestCase):
    async def test_one_result_per_task_in_order(self) -> None:
        worker = StubTool(name="w", handler=_echo)
        with Tapestry() as t:
            OrchestratorWorkers(
                tasks=("t1", "t2", "t3"),
                worker=worker,
                _config=KnotConfig(id="ow"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["ow"]
        assert isinstance(result, OrchestratorWorkersResult)
        assert result.total == 3
        assert result.succeeded == 3
        assert [r.task for r in result.results] == ["t1", "t2", "t3"]
        assert result.results[0].result.result == "done:t1"

    async def test_worker_count_scales_with_task_list(self) -> None:
        worker = StubTool(name="w", handler=_echo)
        tasks = tuple(f"t{i}" for i in range(7))
        with Tapestry() as t:
            OrchestratorWorkers(tasks=tasks, worker=worker, _config=KnotConfig(id="ow"))
        run = await t.run(RunRequest())
        assert len(run.outputs["ow"].results) == 7

    async def test_max_concurrency_bounds_workers(self) -> None:
        probe = _ConcurrencyProbeTool()
        with Tapestry() as t:
            OrchestratorWorkers(
                tasks=tuple(f"t{i}" for i in range(6)),
                worker=probe,
                max_concurrency=2,
                _config=KnotConfig(id="ow"),
            )
        await t.run(RunRequest())
        assert probe.peak <= 2

    async def test_failure_is_isolated(self) -> None:
        worker = StubTool(name="w", handler=_echo)
        with Tapestry() as t:
            OrchestratorWorkers(
                tasks=("ok1", "bad", "ok2"),
                worker=worker,
                _config=KnotConfig(id="ow"),
            )
        run = await t.run(RunRequest())
        result = run.outputs["ow"]
        assert result.succeeded == 2
        statuses = {r.task: r.result.status for r in result.results}
        assert statuses["bad"] is ToolStatus.ERROR
        assert statuses["ok1"] is ToolStatus.OK

    async def test_uses_f7_agent_as_tool(self) -> None:
        reset_doubles()
        with Tapestry():
            agent = StubAgent(_config=KnotConfig(id="worker_agent"), reply="w")
        worker = AgentTool(agent)
        with Tapestry() as t:
            OrchestratorWorkers(
                tasks=("alpha", "beta"),
                worker=worker,
                _config=KnotConfig(id="ow"),
            )
        run = await t.run(RunRequest())
        result = run.outputs["ow"]
        assert result.total == 2
        first = result.results[0].result.result
        assert isinstance(first, AgentResponse)
        assert first.content == "w:alpha"

    async def test_rejects_non_tool_worker(self) -> None:
        with Tapestry():
            knot = OrchestratorWorkers.__new__(OrchestratorWorkers)
            object.__setattr__(knot, "_config", KnotConfig(id="ow"))
        with self.assertRaises(TypeError):
            await knot.process(tasks=("t",), worker="bad")  # type: ignore[arg-type]

    async def test_rejects_bad_max_concurrency(self) -> None:
        with Tapestry():
            knot = OrchestratorWorkers.__new__(OrchestratorWorkers)
            object.__setattr__(knot, "_config", KnotConfig(id="ow"))
        with self.assertRaises(ValueError):
            await knot.process(
                tasks=("t",), worker=StubTool(name="w", handler=_echo), max_concurrency=0
            )
