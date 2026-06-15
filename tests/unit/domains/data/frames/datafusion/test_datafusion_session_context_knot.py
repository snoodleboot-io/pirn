"""Tests for :class:`DatafusionSessionContextKnot`."""

from __future__ import annotations

import unittest

try:
    import datafusion  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("datafusion not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn_data.frames.datafusion.datafusion_session_context import (
    DatafusionSessionContext,
)
from pirn_data.frames.datafusion.datafusion_session_context_knot import (
    DatafusionSessionContextKnot,
)


class TestDatafusionSessionContextKnot(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DatafusionSessionContextKnot:
        return DatafusionSessionContextKnot(_config=KnotConfig(id="test-ctx"))

    async def test_process_returns_datafusion_session_context(self) -> None:
        knot = self._make_knot()
        result = await knot.process()
        assert isinstance(result, DatafusionSessionContext)

    async def test_process_ctx_is_usable(self) -> None:
        knot = self._make_knot()
        result = await knot.process()
        # The wrapped SessionContext should support basic SQL execution
        result.ctx.sql("SELECT 1 AS x")

    async def test_process_returns_fresh_context_each_call(self) -> None:
        knot = self._make_knot()
        first = await knot.process()
        second = await knot.process()
        assert first.ctx is not second.ctx
