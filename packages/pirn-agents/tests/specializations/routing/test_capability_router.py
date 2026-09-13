"""Tests for :class:`CapabilityRouter`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.routing.capability_router import (
    CapabilityRouter,
)
from tests.specializations.conftest import StubLLMProvider


class TestCapabilityRouterProcess(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> CapabilityRouter:
        llm = StubLLMProvider(["data_agent"])
        with Tapestry():
            return CapabilityRouter(
                task="analyse data",
                llm=llm,
                capabilities={"data_agent": "data analysis"},
                _config=KnotConfig(id="capr"),
            )

    async def test_returns_named_agent(self) -> None:
        llm = StubLLMProvider(["data_agent"])
        with Tapestry():
            knot = CapabilityRouter(
                task="analyse data",
                llm=llm,
                capabilities={"data_agent": "data analysis", "text_agent": "text summarisation"},
                _config=KnotConfig(id="capr"),
            )
        result = await knot.process(
            task="analyse sales data",
            llm=llm,
            capabilities={
                "data_agent": "handles data analysis tasks",
                "text_agent": "handles text summarisation",
            },
        )
        assert result == "data_agent"

    async def test_falls_back_to_first_on_unrecognised_label(self) -> None:
        llm = StubLLMProvider(["unknown_agent_xyz"])
        with Tapestry():
            knot = CapabilityRouter(
                task="do something",
                llm=llm,
                capabilities={"alpha": "first agent", "beta": "second agent"},
                _config=KnotConfig(id="capr"),
            )
        result = await knot.process(
            task="do something",
            llm=llm,
            capabilities={"alpha": "first agent", "beta": "second agent"},
        )
        assert result == "alpha"

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["data_agent"])
        with Tapestry():
            knot = CapabilityRouter(
                task="analyse data",
                llm=llm,
                capabilities={"data_agent": "data analysis"},
                _config=KnotConfig(id="capr"),
            )
        result = await knot(
            {
                "task": "analyse data",
                "llm": "not-a-provider",
                "capabilities": {"data_agent": "data analysis"},
            }
        )
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_rejects_empty_capabilities(self) -> None:
        llm = StubLLMProvider(["agent_a"])
        with Tapestry():
            knot = CapabilityRouter(
                task="do something",
                llm=llm,
                capabilities={"a": "desc"},
                _config=KnotConfig(id="capr"),
            )
        with self.assertRaisesRegex(ValueError, "capabilities must be a non-empty"):
            await knot.process(task="do something", llm=llm, capabilities={})

    async def test_rejects_non_string_task(self) -> None:
        llm = StubLLMProvider(["alpha"])
        with Tapestry():
            knot = CapabilityRouter(
                task="do something",
                llm=llm,
                capabilities={"alpha": "does stuff"},
                _config=KnotConfig(id="capr"),
            )
        result = await knot({"task": 123, "llm": llm, "capabilities": {"alpha": "does stuff"}})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"
