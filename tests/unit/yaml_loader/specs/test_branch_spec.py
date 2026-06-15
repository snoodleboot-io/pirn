"""Tests for BranchSpec."""

from __future__ import annotations

import unittest

from pirn.yaml_loader.specs.branch_spec import BranchSpec
from pydantic import ValidationError


class TestBranchSpecConstruction(unittest.TestCase):
    def test_minimal(self) -> None:
        s = BranchSpec(
            id="branch1",
            type="branch",
            input="upstream",
            selector="mymod.selector",
            branches=["left", "right"],
        )
        self.assertEqual(s.input, "upstream")
        self.assertEqual(s.selector, "mymod.selector")
        self.assertEqual(s.branches, ["left", "right"])

    def test_wrong_type_raises(self) -> None:
        with self.assertRaises(ValidationError):
            BranchSpec(
                id="x",
                type="knot",
                input="u",
                selector="fn",
                branches=["a"],
            )

    def test_empty_branches_raises(self) -> None:
        with self.assertRaises(ValidationError):
            BranchSpec(
                id="x",
                type="branch",
                input="u",
                selector="fn",
                branches=[],
            )

    def test_missing_input_raises(self) -> None:
        with self.assertRaises(ValidationError):
            BranchSpec(id="x", type="branch", selector="fn", branches=["a"])

    def test_inherits_validate_io(self) -> None:
        s = BranchSpec(
            id="b",
            type="branch",
            input="up",
            selector="fn",
            branches=["x"],
            validate_io=False,
        )
        self.assertFalse(s.validate_io)
