"""Unit tests for :class:`OrchestratorRouter`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.orchestrator_router import (
    OrchestratorRouter,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestOrchestratorRouterConstruction(unittest.TestCase):
    def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                OrchestratorRouter(
                    task="do thing",
                    llm="bad",  # type: ignore[arg-type]
                    specialist_names=["a"],
                    _config=KnotConfig(id="or"),
                )

    def test_rejects_empty_specialist_names(self) -> None:
        with self.assertRaisesRegex(ValueError, "specialist_names"):
            with Tapestry():
                OrchestratorRouter(
                    task="do thing",
                    llm=StubLLMProvider([]),
                    specialist_names=[],
                    _config=KnotConfig(id="or"),
                )


class TestOrchestratorRouterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_matched_specialist_name(self) -> None:
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

    async def test_falls_back_to_first_on_unknown_name(self) -> None:
        llm = StubLLMProvider(["unknown_specialist"])
        with Tapestry() as t:
            OrchestratorRouter(
                task="task",
                llm=llm,
                specialist_names=["first", "second"],
                _config=KnotConfig(id="or"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["or"] == "first"

    async def test_rejects_non_string_task(self) -> None:
        llm = StubLLMProvider(["first"])
        with Tapestry():
            with self.assertRaises(TypeError):
                OrchestratorRouter(
                    task=42,  # type: ignore[arg-type]
                    llm=llm,
                    specialist_names=["first"],
                    _config=KnotConfig(id="or"),
                )
