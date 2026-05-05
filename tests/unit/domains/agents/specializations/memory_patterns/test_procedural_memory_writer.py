"""Unit tests for :class:`ProceduralMemoryWriter`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.memory_patterns.procedural_memory_writer import (
    ProceduralMemoryWriter,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubMemoryStore


class _TrackingStore(StubMemoryStore):
    def __init__(self):
        super().__init__(hits=[])
        self.stored: dict[str, Any] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.stored[key] = dict(value)


class TestProceduralMemoryWriterConstruction(unittest.TestCase):
    def test_rejects_non_memory_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "MemoryStore"):
            with Tapestry():
                ProceduralMemoryWriter(
                    agent_response=AgentResponse(content="x", finish_reason="stop"),
                    task_description="do thing",
                    store="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="pmw"),
                )


class TestProceduralMemoryWriterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_procedure_key(self) -> None:
        store = _TrackingStore()
        response = AgentResponse(content="step 1, step 2", finish_reason="stop")
        with Tapestry() as t:
            ProceduralMemoryWriter(
                agent_response=response,
                task_description="how to do X",
                store=store,
                _config=KnotConfig(id="pmw"),
            )
        result = await t.run(RunRequest())
        key = result.outputs["pmw"]
        assert key.startswith("procedure:")

    async def test_stores_task_and_response(self) -> None:
        store = _TrackingStore()
        response = AgentResponse(content="steps", finish_reason="stop")
        with Tapestry() as t:
            ProceduralMemoryWriter(
                agent_response=response,
                task_description="deploy app",
                store=store,
                _config=KnotConfig(id="pmw"),
            )
        result = await t.run(RunRequest())
        key = result.outputs["pmw"]
        assert store.stored[key]["task"] == "deploy app"
        assert store.stored[key]["response"] == "steps"

    async def test_rejects_empty_task_description(self) -> None:
        store = _TrackingStore()
        response = AgentResponse(content="x", finish_reason="stop")
        with Tapestry() as t:
            ProceduralMemoryWriter(
                agent_response=response,
                task_description="",
                store=store,
                _config=KnotConfig(id="pmw"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_non_agent_response(self) -> None:
        store = _TrackingStore()
        with Tapestry():
            with self.assertRaises(TypeError):
                ProceduralMemoryWriter(
                    agent_response="not-a-response",  # type: ignore[arg-type]
                    task_description="task",
                    store=store,
                    _config=KnotConfig(id="pmw"),
                )
