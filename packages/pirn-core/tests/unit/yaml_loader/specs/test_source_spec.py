"""Tests for SourceSpec."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from pirn.yaml_loader.specs.source_spec import SourceSpec


class TestSourceSpecConstruction(unittest.TestCase):
    def test_minimal(self) -> None:
        s = SourceSpec(id="src1", type="source", callable="mymod.MySource")
        self.assertEqual(s.id, "src1")
        self.assertEqual(s.type, "source")
        self.assertEqual(s.callable, "mymod.MySource")

    def test_with_description_and_tags(self) -> None:
        s = SourceSpec(
            id="src2",
            type="source",
            callable="mymod.fn",
            description="reads csv",
            tags=["io", "read"],
        )
        self.assertEqual(s.description, "reads csv")
        self.assertEqual(s.tags, ["io", "read"])

    def test_wrong_type_raises(self) -> None:
        with self.assertRaises(ValidationError):
            SourceSpec(id="x", type="sink", callable="fn")

    def test_missing_callable_raises(self) -> None:
        with self.assertRaises(ValidationError):
            SourceSpec(id="x", type="source")

    def test_extra_fields_forbidden(self) -> None:
        with self.assertRaises(ValidationError):
            SourceSpec(id="x", type="source", callable="fn", extra_field="bad")
