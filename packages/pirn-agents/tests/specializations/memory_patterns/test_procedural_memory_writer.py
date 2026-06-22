"""Unit tests for :class:`ProceduralMemoryWriter`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.memory_patterns.procedural_memory_writer import (
    ProceduralMemoryWriter,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry

from tests.specializations.conftest import StubMemoryStore


class _TrackingStore(StubMemoryStore):
    def __init__(self):
        super().__init__(hits=[])
        self.stored: dict[str, Any] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.stored[key] = dict(value)


def _make_knot() -> ProceduralMemoryWriter:
    with Tapestry():
        return ProceduralMemoryWriter(
            agent_response=AgentResponse(content="x", finish_reason="stop"),
            task_description="task",
            store=_TrackingStore(),
            _config=KnotConfig(id="pmw"),
        )


class TestProceduralMemoryWriterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_procedure_key(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        response = AgentResponse(content="step 1, step 2", finish_reason="stop")
        key = await k.process(agent_response=response, task_description="how to do X", store=store)
        assert key.startswith("procedure:")

    async def test_stores_task_and_response(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        response = AgentResponse(content="steps", finish_reason="stop")
        key = await k.process(agent_response=response, task_description="deploy app", store=store)
        assert store.stored[key]["task"] == "deploy app"
        assert store.stored[key]["response"] == "steps"

    async def test_rejects_empty_task_description(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        response = AgentResponse(content="x", finish_reason="stop")
        with self.assertRaises(ValueError):
            await k.process(agent_response=response, task_description="", store=store)

    async def test_rejects_non_agent_response(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        with self.assertRaises(TypeError):
            await k.process(agent_response="not-a-response", task_description="task", store=store)  # type: ignore[arg-type]

    async def test_rejects_non_memory_store(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="x", finish_reason="stop")
        with self.assertRaises(TypeError):
            await k.process(agent_response=response, task_description="task", store="bad")  # type: ignore[arg-type]
