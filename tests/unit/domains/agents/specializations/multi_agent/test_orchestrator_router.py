"""Unit tests for :class:`OrchestratorRouter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.multi_agent.orchestrator_router import (
    OrchestratorRouter,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


def _make_knot() -> OrchestratorRouter:
    with Tapestry():
        return OrchestratorRouter(
            task="do thing",
            llm=StubLLMProvider(["first"]),
            specialist_names=["first"],
            _config=KnotConfig(id="or"),
        )


class TestOrchestratorRouterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_matched_specialist_name(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["sql_expert"])
        result = await k.process(task="write a SQL query", llm=llm, specialist_names=["sql_expert", "code_writer"])
        assert result == "sql_expert"

    async def test_falls_back_to_first_on_unknown_name(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["unknown_specialist"])
        result = await k.process(task="task", llm=llm, specialist_names=["first", "second"])
        assert result == "first"

    async def test_rejects_non_llm_provider(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(task="task", llm="bad", specialist_names=["first"])  # type: ignore[arg-type]

    async def test_rejects_empty_specialist_names(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["first"])
        with self.assertRaises(ValueError):
            await k.process(task="task", llm=llm, specialist_names=[])

    async def test_tapestry_run_integration(self) -> None:
        llm = StubLLMProvider(["sql_expert"])
        with Tapestry() as t:
            OrchestratorRouter(
                task="write a SQL query",
                llm=llm,
                specialist_names=["sql_expert", "code_writer"],
                _config=KnotConfig(id="or"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["or"] == "sql_expert"
