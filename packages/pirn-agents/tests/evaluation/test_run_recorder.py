"""Tests for the F29 record/replay seam (:class:`RunRecorder`)."""

from __future__ import annotations

import unittest
from collections.abc import Awaitable, Callable
from typing import Any

from pirn_agents.evaluation.null_run_recorder import NullRunRecorder
from pirn_agents.evaluation.run_recorder import RunRecorder


class NullRunRecorderTests(unittest.IsolatedAsyncioTestCase):
    async def test_executes_thunk_live(self) -> None:
        calls: list[str] = []

        async def _thunk() -> str:
            calls.append("ran")
            return "result"

        out = await NullRunRecorder().invoke(key="k", thunk=_thunk)
        assert out == "result"
        assert calls == ["ran"]

    async def test_base_interface_is_abstract(self) -> None:
        async def _thunk() -> int:
            return 1

        factory: Callable[[], Awaitable[Any]] = _thunk
        with self.assertRaises(NotImplementedError):
            await RunRecorder().invoke(key="k", thunk=factory)


if __name__ == "__main__":
    unittest.main()
