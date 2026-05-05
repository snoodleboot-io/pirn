"""Tests for :class:`CapabilityRouter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.routing.capability_router import (
    CapabilityRouter,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestCapabilityRouterConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            with Tapestry():
                CapabilityRouter(
                    task="analyse data",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    capabilities={"agent_a": "data analysis"},
                    _config=KnotConfig(id="capr"),
                )

    async def test_rejects_empty_capabilities(self) -> None:
        llm = StubLLMProvider(["agent_a"])
        with self.assertRaisesRegex(ValueError, "capabilities must be a non-empty"):
            with Tapestry():
                CapabilityRouter(
                    task="do something",
                    llm=llm,
                    capabilities={},
                    _config=KnotConfig(id="capr"),
                )


class TestCapabilityRouterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_named_agent(self) -> None:
        llm = StubLLMProvider(["data_agent"])
        with Tapestry() as t:
            CapabilityRouter(
                task="analyse sales data",
                llm=llm,
                capabilities={
                    "data_agent": "handles data analysis tasks",
                    "text_agent": "handles text summarisation",
                },
                _config=KnotConfig(id="capr"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["capr"] == "data_agent"

    async def test_falls_back_to_first_on_unrecognised_label(self) -> None:
        llm = StubLLMProvider(["unknown_agent_xyz"])
        with Tapestry() as t:
            CapabilityRouter(
                task="do something",
                llm=llm,
                capabilities={
                    "alpha": "first agent",
                    "beta": "second agent",
                },
                _config=KnotConfig(id="capr"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["capr"] == "alpha"

    async def test_rejects_non_string_task(self) -> None:
        llm = StubLLMProvider(["alpha"])
        with self.assertRaises(TypeError):
            with Tapestry():
                CapabilityRouter(
                    task=123,  # type: ignore[arg-type]
                    llm=llm,
                    capabilities={"alpha": "does stuff"},
                    _config=KnotConfig(id="capr"),
                )
