"""Tests for :class:`ReflexionPipeline`, including memory read/write."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.reflexion.reflexion_pipeline import ReflexionPipeline
from pirn_agents.specializations.reflexion.reflexion_result import ReflexionResult
from tests.specializations.conftest import StubLLMProvider


class DictMemoryStore(MemoryStore):
    """A functional in-memory store recording reads and writes."""

    def __init__(self) -> None:
        self.data: dict[str, Mapping[str, Any]] = {}
        self.reads: list[str] = []
        self.writes: list[str] = []

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.data[key] = dict(value)
        self.writes.append(key)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        self.reads.append(key)
        return self.data.get(key)

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            return
            yield {}

        return _aiter()

    async def forget(self, key: str) -> None:
        self.data.pop(key, None)

    async def close(self) -> None:
        return None


class TestReflexionPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_succeeds_on_first_attempt(self) -> None:
        llm = StubLLMProvider(["answer", "PASS"])
        with Tapestry() as t:
            ReflexionPipeline(
                task="q", llm=llm, memory=DictMemoryStore(), _config=KnotConfig(id="rx")
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["rx"]
        assert isinstance(result, ReflexionResult)
        assert result.succeeded is True
        assert result.iterations == 1
        assert result.answer == "answer"

    async def test_reflection_written_and_read_back(self) -> None:
        # iter1: actor a1, eval FAIL, reflect "be longer"; iter2: actor a2, eval PASS
        llm = StubLLMProvider(["a1", "FAIL: too short", "be longer", "a2", "PASS"])
        store = DictMemoryStore()
        with Tapestry() as t:
            ReflexionPipeline(task="q", llm=llm, memory=store, _config=KnotConfig(id="rx"))
        run = await t.run(RunRequest())
        result = run.outputs["rx"]
        assert result.succeeded is True
        assert result.iterations == 2
        # Reflection was persisted to memory ...
        assert "reflexion:0" in store.writes
        assert store.data["reflexion:0"]["text"] == "be longer"
        # ... and read back on the second iteration (fed into the actor prompt).
        assert "reflexion:0" in store.reads
        second_actor_call = llm.calls[3]
        assert "be longer" in second_actor_call[0]["content"]

    async def test_exhausts_iterations_without_success(self) -> None:
        llm = StubLLMProvider(["a1", "FAIL: x", "r1", "a2", "FAIL: y", "r2"])
        store = DictMemoryStore()
        with Tapestry() as t:
            ReflexionPipeline(
                task="q",
                llm=llm,
                memory=store,
                max_iterations=2,
                _config=KnotConfig(id="rx"),
            )
        run = await t.run(RunRequest())
        result = run.outputs["rx"]
        assert result.succeeded is False
        assert result.iterations == 2
        assert len(result.attempts) == 2

    async def test_rejects_non_memory_store(self) -> None:
        llm = StubLLMProvider(["a", "PASS"])
        with Tapestry():
            knot = ReflexionPipeline.__new__(ReflexionPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="rx"))
        with self.assertRaises(TypeError):
            await knot.process(task="q", llm=llm, memory="bad")  # type: ignore[arg-type]

    async def test_rejects_non_positive_iterations(self) -> None:
        llm = StubLLMProvider(["a", "PASS"])
        with Tapestry():
            knot = ReflexionPipeline.__new__(ReflexionPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="rx"))
        with self.assertRaises(ValueError):
            await knot.process(task="q", llm=llm, memory=DictMemoryStore(), max_iterations=0)
