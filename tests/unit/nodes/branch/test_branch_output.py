"""Unit tests for BranchOutput."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.nodes.branch.branch import Branch
from pirn.nodes.branch.branch_output import BranchOutput
from pirn.nodes.sink import Sink
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _Capture(Sink):
    async def process(self, data: Any, **_: Any) -> None:
        pass


class _ValSource(Source):
    def __init__(self, *, value: Any, **kwargs: Any) -> None:
        self._value = value
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> Any:
        return self._value


class TestBranchOutputConstruction(unittest.TestCase):
    def test_branch_output_created_by_branch(self) -> None:
        with Tapestry():
            src = _ValSource(value=10, _config=KnotConfig(id="src"))
            branch = Branch(
                input=src,
                selector=lambda v: "a",
                branches=("a", "b"),
                _config=KnotConfig(id="br"),
            )
        self.assertIsInstance(branch["a"], BranchOutput)
        self.assertIsInstance(branch["b"], BranchOutput)


class TestBranchOutputProcess(unittest.IsolatedAsyncioTestCase):
    async def test_selected_branch_receives_value(self) -> None:
        with Tapestry() as t:
            src = _ValSource(value=42, _config=KnotConfig(id="src"))
            branch = Branch(
                input=src,
                selector=lambda v: "left",
                branches=("left", "right"),
                _config=KnotConfig(id="br"),
            )
            _Capture(data=branch["left"], _config=KnotConfig(id="cap"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)

    async def test_unselected_branch_is_skipped(self) -> None:
        with Tapestry() as t:
            src = _ValSource(value=42, _config=KnotConfig(id="src"))
            branch = Branch(
                input=src,
                selector=lambda v: "left",
                branches=("left", "right"),
                _config=KnotConfig(id="br"),
            )
            _Capture(data=branch["right"], _config=KnotConfig(id="cap_r"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertNotIn("cap_r", result.outputs)
