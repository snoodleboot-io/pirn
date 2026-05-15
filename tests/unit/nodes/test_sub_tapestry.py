"""Unit tests for SubTapestry and SubTapestryError."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.managers.exception_record import ExceptionRecord
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry, SubTapestryError
from pirn.tapestry import Tapestry




def _make_failed_result() -> RunResult:
    exc = ExceptionRecord(
        run_id="r", knot_id="fail", exc_type="RuntimeError",
        message="inner failure", traceback_text="",
    )
    return RunResult(
        run_id="r", terminals_requested=["fail"], outputs={},
        exceptions=[exc], started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC), dispatcher="local",
    )


class TestSubTapestryError(unittest.TestCase):
    def test_message_includes_exception_count_and_run_id(self) -> None:
        result = _make_failed_result()
        err = SubTapestryError(result)
        self.assertIn("1", str(err))
        self.assertIn("r", str(err))

    def test_inner_result_accessible(self) -> None:
        result = _make_failed_result()
        err = SubTapestryError(result)
        self.assertIs(err.inner_result, result)


class _DoubleSource(Source):
    async def process(self, **_: Any) -> int:
        return 21


class _InnerPipeline(SubTapestry):
    async def process(self, upstream: Any, **_: Any) -> Any:
        from pirn.nodes.source import Source as _Source

        class _PassThrough(_Source):
            async def process(self, **_kw: Any) -> Any:
                return upstream * 2

        return _PassThrough(_config=KnotConfig(id="pt"))


class TestSubTapestryProcess(unittest.IsolatedAsyncioTestCase):
    async def test_run_inner_runs_inner_tapestry(self) -> None:
        with Tapestry() as t:
            src = _DoubleSource(_config=KnotConfig(id="src"))
            _InnerPipeline(upstream=src, _config=KnotConfig(id="pipeline"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["pipeline"], 42)

    async def test_base_process_raises_not_implemented(self) -> None:
        class _Bare(SubTapestry):
            pass

        with Tapestry() as t:
            src = _DoubleSource(_config=KnotConfig(id="src2"))
            _Bare(upstream=src, _config=KnotConfig(id="bare"))
        result = await t.run(RunRequest())
        self.assertFalse(result.succeeded)
