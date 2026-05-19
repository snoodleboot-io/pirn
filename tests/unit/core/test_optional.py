"""Tests for :class:`Optional` decorator."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.optional import Optional
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.tapestry import Tapestry


class _AlwaysSucceed(Knot):
    async def process(self, **_: Any) -> int:
        return 42


class _AlwaysFail(Knot):
    async def process(self, **_: Any) -> int:
        raise RuntimeError("boom")


class _RequiresReal(Knot):
    def __init__(self, *, value: str, _config: KnotConfig, **kwargs: Any) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError("value must be a non-empty string")
        super().__init__(value=value, _config=_config, **kwargs)

    async def process(self, value: str = "", **_: Any) -> str:
        return value


class TestOptionalDecoratorForm(unittest.TestCase):
    def test_is_optional_on_success(self) -> None:
        with Tapestry():
            opt = Optional(_AlwaysSucceed, _config=KnotConfig(id="opt"))
        assert isinstance(opt, Optional)

    def test_is_instance_of_target_class_on_success(self) -> None:
        with Tapestry():
            opt = Optional(_AlwaysSucceed, _config=KnotConfig(id="opt"))
        assert isinstance(opt, _AlwaysSucceed)

    def test_construction_failure_returns_stub(self) -> None:
        with Tapestry():
            opt = Optional(_RequiresReal, value="", _config=KnotConfig(id="opt"))
        assert isinstance(opt, Optional)
        assert opt.knot_id == "opt"

    def test_stub_has_target_class_name(self) -> None:
        with Tapestry():
            opt = Optional(_RequiresReal, value="", _config=KnotConfig(id="opt"))
        assert type(opt).__name__ == "_RequiresReal"

    def test_non_knot_class_produces_stub(self) -> None:
        with Tapestry():
            opt = Optional(int, _config=KnotConfig(id="opt"))  # type: ignore[arg-type]
        assert isinstance(opt, Optional)


class TestOptionalRuntime(unittest.IsolatedAsyncioTestCase):
    async def test_passes_value_through_on_success(self) -> None:
        with Tapestry() as t:
            Optional(_AlwaysSucceed, _config=KnotConfig(id="opt"))
        result = await t.run(RunRequest())
        assert result.outputs["opt"] == 42

    async def test_always_succeeds_on_process_failure(self) -> None:
        with Tapestry() as t:
            Optional(_AlwaysFail, _config=KnotConfig(id="opt"))
        result = await t.run(RunRequest())
        assert "opt" in result.outputs
        assert "opt" not in result.skipped

    async def test_process_failure_produces_skipped_value(self) -> None:
        with Tapestry() as t:
            Optional(_AlwaysFail, _config=KnotConfig(id="opt"))
        result = await t.run(RunRequest())
        assert isinstance(result.outputs["opt"], Skipped)

    async def test_process_failure_captures_error_in_detail(self) -> None:
        with Tapestry() as t:
            Optional(_AlwaysFail, _config=KnotConfig(id="opt"))
        result = await t.run(RunRequest())
        skipped = result.outputs["opt"]
        assert isinstance(skipped, Skipped)
        assert skipped.detail["error"] == "RuntimeError"
        assert "boom" in skipped.detail["message"]
        assert skipped.detail["phase"] == "execution"

    async def test_construction_failure_produces_skipped_value(self) -> None:
        with Tapestry() as t:
            Optional(_RequiresReal, value="", _config=KnotConfig(id="opt"))
        result = await t.run(RunRequest())
        assert isinstance(result.outputs["opt"], Skipped)

    async def test_construction_failure_captures_error_in_detail(self) -> None:
        with Tapestry() as t:
            Optional(_RequiresReal, value="", _config=KnotConfig(id="opt"))
        result = await t.run(RunRequest())
        skipped = result.outputs["opt"]
        assert isinstance(skipped, Skipped)
        assert skipped.detail["phase"] == "construction"
        assert skipped.detail["error"] == "ValueError"

    async def test_downstream_receives_skipped_value(self) -> None:
        @knot
        async def use(x: Any) -> bool:
            return isinstance(x, Skipped)

        with Tapestry() as t:
            opt = Optional(_AlwaysFail, _config=KnotConfig(id="opt"))
            use(x=opt, _config=KnotConfig(id="use"))
        result = await t.run(RunRequest())
        assert result.outputs["use"] is True
