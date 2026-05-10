"""Tests for :class:`Optional` wrapper knot."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.optional import Optional
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry


@knot
async def always_succeed() -> int:
    return 42


@knot
async def always_fail() -> int:
    raise RuntimeError("boom")


class TestOptionalConstruction(unittest.TestCase):
    def test_rejects_non_knot(self) -> None:
        with self.assertRaises(TypeError):
            Optional(knot="not_a_knot", _config=KnotConfig(id="opt"))  # type: ignore[arg-type]

    def test_is_optional(self) -> None:
        with Tapestry():
            inner = always_succeed(_config=KnotConfig(id="inner"))
            opt = Optional(knot=inner, _config=KnotConfig(id="opt"))
        assert isinstance(opt, Optional)


class TestOptionalPassthrough(unittest.IsolatedAsyncioTestCase):
    async def test_passes_value_through_on_success(self) -> None:
        with Tapestry() as t:
            inner = always_succeed(_config=KnotConfig(id="inner"))
            Optional(knot=inner, _config=KnotConfig(id="opt"))
        result = await t.run(RunRequest())
        assert result.outputs["opt"] == 42

    async def test_produces_skipped_on_failure(self) -> None:
        with Tapestry() as t:
            inner = always_fail(_config=KnotConfig(id="inner"))
            Optional(knot=inner, _config=KnotConfig(id="opt"))
        result = await t.run(RunRequest())
        assert "opt" in result.skipped

    async def test_downstream_skips_when_optional_skips(self) -> None:
        @knot
        async def use(x: int) -> int:
            return x + 1

        with Tapestry() as t:
            inner = always_fail(_config=KnotConfig(id="inner"))
            opt = Optional(knot=inner, _config=KnotConfig(id="opt"))
            use(x=opt, _config=KnotConfig(id="use"))
        result = await t.run(RunRequest())
        assert "opt" in result.skipped
        assert "use" in result.skipped
