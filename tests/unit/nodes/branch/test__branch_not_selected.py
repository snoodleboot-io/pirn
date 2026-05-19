"""Unit tests for _BranchNotSelectedError."""

from __future__ import annotations

import unittest

from pirn.nodes.branch._branch_not_selected import _BranchNotSelectedError


class TestBranchNotSelected(unittest.TestCase):
    def test_is_exception(self) -> None:
        self.assertTrue(issubclass(_BranchNotSelectedError, Exception))

    def test_instantiates_with_branch_name(self) -> None:
        exc = _BranchNotSelectedError("path_a")
        self.assertIsInstance(exc, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        with self.assertRaises(_BranchNotSelectedError):
            raise _BranchNotSelectedError("path_b")
