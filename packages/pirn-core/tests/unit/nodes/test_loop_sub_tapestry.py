"""Unit tests for LoopSubTapestry."""

from __future__ import annotations

import unittest
from typing import TYPE_CHECKING, Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class _InitSource(Source):
    def __init__(self, *, init_state: Any, **kwargs: Any) -> None:
        self._init = init_state
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> Any:
        return self._init


class _CounterLoop(LoopSubTapestry[int]):
    """Counts up to a target by incrementing state each iteration."""

    def __init__(self, *, target: int, **kwargs: Any) -> None:
        self._target = target
        super().__init__(**kwargs)

    def step(self, state: int) -> tuple[Tapestry, int] | None:
        if state >= self._target:
            return None

        class _IncrSource(Source):
            def __init__(cls_self, *, val: int, **kw: Any) -> None:
                cls_self._val = val
                super().__init__(**kw)

            async def process(self, **_: Any) -> int:
                return self._val + 1

        t = Tapestry()
        with t:
            _IncrSource(val=state, _config=KnotConfig(id="incr"))
        return t, state + 1

    def fold(self, state: int, result: RunResult) -> int:
        return result.outputs["incr"]


class TestLoopSubTapestryConstruction(unittest.TestCase):
    def test_constructs_as_sub_tapestry(self) -> None:
        with Tapestry():
            src = _InitSource(init_state=0, _config=KnotConfig(id="init"))
            loop = _CounterLoop(target=3, state=src, _config=KnotConfig(id="loop"))
        self.assertIsNotNone(loop)

    def test_step_id_default(self) -> None:
        loop = _CounterLoop.__new__(_CounterLoop)
        loop._target = 5
        self.assertEqual(loop.step_id(0, 1), "step_1")
        self.assertEqual(loop.step_id(0, 42), "step_42")


class TestLoopSubTapestryProcess(unittest.IsolatedAsyncioTestCase):
    async def test_loop_runs_to_completion(self) -> None:
        with Tapestry() as t:
            src = _InitSource(init_state=0, _config=KnotConfig(id="init"))
            _CounterLoop(target=3, state=src, _config=KnotConfig(id="loop"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["loop"], 3)

    async def test_loop_with_zero_iterations(self) -> None:
        """When step returns None immediately, loop returns initial state."""
        with Tapestry() as t:
            src = _InitSource(init_state=5, _config=KnotConfig(id="init"))
            _CounterLoop(target=0, state=src, _config=KnotConfig(id="loop"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["loop"], 5)
