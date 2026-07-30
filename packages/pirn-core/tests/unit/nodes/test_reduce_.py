"""Unit tests for Reduce."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.reduce_ import Reduce
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _ListSource(Source):
    def __init__(self, *, items: list, **kwargs: Any) -> None:
        self._items = items
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> list:
        return self._items


class TestReduceConstruction(unittest.TestCase):
    def test_rejects_non_knot_of(self) -> None:
        with self.assertRaisesRegex(TypeError, "'of' must be a Knot"):
            with Tapestry():
                Reduce(of=42, combine=sum, _config=KnotConfig(id="r"))  # type: ignore

    def test_rejects_non_callable_combine(self) -> None:
        with self.assertRaisesRegex(TypeError, "'combine' must be callable"):
            with Tapestry():
                src = _ListSource(items=[1], _config=KnotConfig(id="src"))
                Reduce(of=src, combine="not_callable", _config=KnotConfig(id="r"))

    def test_pairwise_requires_initial(self) -> None:
        with self.assertRaisesRegex(TypeError, "initial"):
            with Tapestry():
                src = _ListSource(items=[1], _config=KnotConfig(id="src"))
                Reduce(
                    of=src,
                    combine=lambda acc, x: acc + x,
                    _config=KnotConfig(id="r"),
                )

    def test_rejects_combine_with_zero_required_args(self) -> None:
        with self.assertRaisesRegex(TypeError, "1 or 2 required args"):
            with Tapestry():
                src = _ListSource(items=[1], _config=KnotConfig(id="src"))
                Reduce(of=src, combine=lambda: 0, _config=KnotConfig(id="r"))

    def test_requires_config(self) -> None:
        with self.assertRaisesRegex(TypeError, "_config"):
            with Tapestry():
                src = _ListSource(items=[1], _config=KnotConfig(id="src"))
                Reduce(of=src, combine=sum)


class TestReduceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_whole_list_sum(self) -> None:
        with Tapestry() as t:
            src = _ListSource(items=[1, 2, 3, 4], _config=KnotConfig(id="src"))
            Reduce(of=src, combine=sum, _config=KnotConfig(id="r"))
        result = await t.run(RunRequest())
        self.assertEqual(result.outputs["r"], 10)

    async def test_pairwise_reduce(self) -> None:
        with Tapestry() as t:
            src = _ListSource(items=[1, 2, 3], _config=KnotConfig(id="src"))
            Reduce(
                of=src,
                combine=lambda acc, x: acc + x,
                initial=0,
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        self.assertEqual(result.outputs["r"], 6)

    async def test_pairwise_reduce_dict_fold(self) -> None:
        with Tapestry() as t:
            src = _ListSource(items=["a", "b", "a"], _config=KnotConfig(id="src"))
            Reduce(
                of=src,
                combine=lambda acc, w: {**acc, w: acc.get(w, 0) + 1},
                initial={},
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        self.assertEqual(result.outputs["r"], {"a": 2, "b": 1})


class TestReduceAsyncCombine(unittest.IsolatedAsyncioTestCase):
    """An ``async def combine`` must be awaited, not emitted as a coroutine.

    Both forms invoked combine synchronously, so an async combine made the node
    output a coroutine object — silently, because a coroutine is a perfectly
    good ``Any``. Downstream saw ``<coroutine object ...>`` where the reduced
    value belonged. See PIR-768.
    """

    async def test_whole_form_awaits(self) -> None:
        async def combine(items: list[int]) -> int:
            return sum(items)

        with Tapestry() as t:
            src = _ListSource(items=[1, 2, 3], _config=KnotConfig(id="src"))
            Reduce(of=src, combine=combine, _config=KnotConfig(id="r"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["r"], 6)

    async def test_pairwise_form_awaits_every_step(self) -> None:
        async def combine(acc: int, item: int) -> int:
            return acc + item

        with Tapestry() as t:
            src = _ListSource(items=[1, 2, 3], _config=KnotConfig(id="src"))
            Reduce(of=src, combine=combine, initial=0, _config=KnotConfig(id="r"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        # Not just the final await: an unawaited step would feed a coroutine
        # into the next iteration as the accumulator.
        self.assertEqual(result.outputs["r"], 6)

    async def test_async_dunder_call_object_is_detected(self) -> None:
        """A callable object whose ``__call__`` is async is the case that
        motivated detecting with ``inspect`` rather than ``asyncio``."""

        class _AsyncSummer:
            async def __call__(self, items: list[int]) -> int:
                return sum(items)

        with Tapestry() as t:
            src = _ListSource(items=[4, 5], _config=KnotConfig(id="src"))
            Reduce(of=src, combine=_AsyncSummer(), _config=KnotConfig(id="r"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["r"], 9)

    async def test_sync_combine_still_not_awaited(self) -> None:
        with Tapestry() as t:
            src = _ListSource(items=[1, 2, 3], _config=KnotConfig(id="src"))
            Reduce(of=src, combine=sum, _config=KnotConfig(id="r"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["r"], 6)
