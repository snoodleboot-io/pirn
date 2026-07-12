"""Unit tests for :func:`merge_profile_fields`."""

from __future__ import annotations

import unittest

from pirn_agents.memory_management.profile_merge import merge_profile_fields


class TestMergeProfileFields(unittest.TestCase):
    def test_preserves_unrelated_existing_fields(self) -> None:
        merged = merge_profile_fields({"name": "Ada", "age": 30}, {"age": 31})
        assert merged == {"name": "Ada", "age": 31}

    def test_adds_new_fields(self) -> None:
        merged = merge_profile_fields({"a": 1}, {"b": 2})
        assert merged == {"a": 1, "b": 2}

    def test_deep_merges_nested_mappings(self) -> None:
        merged = merge_profile_fields(
            {"prefs": {"theme": "dark", "lang": "en"}},
            {"prefs": {"theme": "light"}},
        )
        assert merged == {"prefs": {"theme": "light", "lang": "en"}}

    def test_does_not_mutate_inputs(self) -> None:
        existing = {"a": 1}
        incoming = {"b": 2}
        merge_profile_fields(existing, incoming)
        assert existing == {"a": 1} and incoming == {"b": 2}

    def test_rejects_non_mapping(self) -> None:
        with self.assertRaises(TypeError):
            merge_profile_fields({}, "bad")  # type: ignore[arg-type]
