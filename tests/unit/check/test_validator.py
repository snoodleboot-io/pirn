"""Tests for validate_tapestry."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.check.validator import validate_tapestry


def _make_mock_knot(knot_id: str, parents: dict | None = None, klass=None):
    """Build a mock knot with the given id and parents dict."""
    knot = MagicMock()
    knot.knot_id = knot_id
    knot.parents = parents or {}
    knot.__class__ = klass or object
    return knot


def _make_tapestry(*knots):
    t = MagicMock()
    t._store.all.return_value = list(knots)
    return t


class TestValidateTapestryEmpty(unittest.TestCase):
    def test_empty_tapestry_warns(self) -> None:
        tapestry = _make_tapestry()
        result = validate_tapestry(tapestry)
        self.assertTrue(result.ok)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("no knots", result.warnings[0].message)


class TestValidateTapestryDuplicateIds(unittest.TestCase):
    def test_duplicate_knot_id_error(self) -> None:
        k1 = _make_mock_knot("dup")
        k2 = _make_mock_knot("dup")
        tapestry = _make_tapestry(k1, k2)
        result = validate_tapestry(tapestry)
        self.assertFalse(result.ok)
        ids = [i.knot_id for i in result.errors]
        self.assertIn("dup", ids)


class TestValidateTapestryValid(unittest.TestCase):
    def test_single_knot_ok(self) -> None:
        k1 = _make_mock_knot("src")
        tapestry = _make_tapestry(k1)
        result = validate_tapestry(tapestry)
        self.assertTrue(result.ok)

    def test_two_knots_with_parent(self) -> None:
        k1 = _make_mock_knot("src")
        k2 = _make_mock_knot("transform", parents={"k1": "src"})
        tapestry = _make_tapestry(k1, k2)
        result = validate_tapestry(tapestry)
        self.assertTrue(result.ok)


class TestValidateTapestryManyTerminals(unittest.TestCase):
    def test_four_or_fewer_terminals_no_warning(self) -> None:
        knots = [_make_mock_knot(f"t{i}") for i in range(3)]
        tapestry = _make_tapestry(*knots)
        result = validate_tapestry(tapestry)
        warning_msgs = [i.message for i in result.warnings]
        self.assertFalse(any("terminal" in m for m in warning_msgs))

    def test_many_terminals_warns(self) -> None:
        from pirn.check.validation_issue import ValidationIssue
        knots = [_make_mock_knot(f"t{i}") for i in range(5)]
        tapestry = _make_tapestry(*knots)
        result = validate_tapestry(tapestry)
        warning_msgs = [i.message for i in result.warnings]
        self.assertTrue(any("terminal" in m for m in warning_msgs))
