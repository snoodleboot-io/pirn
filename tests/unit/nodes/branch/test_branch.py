"""Unit tests for Branch."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.branch.branch import Branch
from pirn.nodes.branch.branch_output import BranchOutput
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _ValSource(Source):
    def __init__(self, *, value: Any, **kwargs: Any) -> None:
        self._value = value
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> Any:
        return self._value


class TestBranchConstruction(unittest.TestCase):
    def test_rejects_non_knot_input(self) -> None:
        with self.assertRaisesRegex(TypeError, "'input' must be a Knot"):
            with Tapestry():
                Branch(input=42, selector=lambda v: "a", branches=("a",), _config=KnotConfig(id="br"))

    def test_rejects_non_callable_selector(self) -> None:
        with self.assertRaisesRegex(TypeError, "'selector' must be callable"):
            with Tapestry():
                src = _ValSource(value=1, _config=KnotConfig(id="src"))
                Branch(input=src, selector="not_callable", branches=("a",), _config=KnotConfig(id="br"))

    def test_rejects_empty_branches(self) -> None:
        with self.assertRaisesRegex(TypeError, "at least one branch"):
            with Tapestry():
                src = _ValSource(value=1, _config=KnotConfig(id="src"))
                Branch(input=src, selector=lambda v: "a", branches=(), _config=KnotConfig(id="br"))

    def test_rejects_duplicate_branch_names(self) -> None:
        with self.assertRaisesRegex(TypeError, "duplicate"):
            with Tapestry():
                src = _ValSource(value=1, _config=KnotConfig(id="src"))
                Branch(input=src, selector=lambda v: "a", branches=("a", "a"), _config=KnotConfig(id="br"))

    def test_requires_config(self) -> None:
        with self.assertRaisesRegex(TypeError, "_config"):
            with Tapestry():
                src = _ValSource(value=1, _config=KnotConfig(id="src"))
                Branch(input=src, selector=lambda v: "a", branches=("a",))

    def test_branch_names_property(self) -> None:
        with Tapestry():
            src = _ValSource(value=1, _config=KnotConfig(id="src"))
            branch = Branch(
                input=src, selector=lambda v: "a",
                branches=("a", "b"), _config=KnotConfig(id="br"),
            )
        self.assertEqual(branch.branch_names, ("a", "b"))

    def test_getitem_returns_branch_output(self) -> None:
        with Tapestry():
            src = _ValSource(value=1, _config=KnotConfig(id="src"))
            branch = Branch(
                input=src, selector=lambda v: "a",
                branches=("a", "b"), _config=KnotConfig(id="br"),
            )
        self.assertIsInstance(branch["a"], BranchOutput)

    def test_getitem_raises_for_unknown_name(self) -> None:
        with Tapestry():
            src = _ValSource(value=1, _config=KnotConfig(id="src"))
            branch = Branch(
                input=src, selector=lambda v: "a",
                branches=("a",), _config=KnotConfig(id="br"),
            )
        with self.assertRaises(KeyError):
            _ = branch["missing"]


class TestBranchProcess(unittest.IsolatedAsyncioTestCase):
    async def test_selector_routes_correctly(self) -> None:
        with Tapestry() as t:
            src = _ValSource(value="hello", _config=KnotConfig(id="src"))
            branch = Branch(
                input=src,
                selector=lambda v: "upper" if isinstance(v, str) else "lower",
                branches=("upper", "lower"),
                _config=KnotConfig(id="br"),
            )
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["br"], "upper")

    async def test_selector_invalid_return_fails(self) -> None:
        with Tapestry() as t:
            src = _ValSource(value=1, _config=KnotConfig(id="src"))
            Branch(
                input=src,
                selector=lambda v: "not_a_declared_branch",
                branches=("a", "b"),
                _config=KnotConfig(id="br"),
            )
        result = await t.run(RunRequest())
        self.assertFalse(result.succeeded)
