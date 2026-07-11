"""Tests for the extras capability probe (F2-S6 / PIR-143).

:func:`pirn_agents.capability_probe.available_extras` must report import
availability for every extra WITHOUT importing a backend and WITHOUT raising,
regardless of what is actually installed. These tests stub
``importlib.util.find_spec`` (patched where ``capability_probe`` references it)
to simulate all-present, all-missing, and probe-raising environments.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from pirn_agents.capability_probe import available_extras

_LEAF_EXTRAS = {
    "openai",
    "anthropic",
    "qdrant",
    "pgvector",
    "chroma",
    "neo4j",
    "kuzu",
    "local-embed",
    "cross-encoder",
    "web",
    "mcp",
    "sql",
    "otel",
    "grammar",
}
_BUNDLE_EXTRAS = {"llm", "vector", "all"}
_EXPECTED_EXTRAS = _LEAF_EXTRAS | _BUNDLE_EXTRAS

_FIND_SPEC = "pirn_agents.capability_probe.importlib.util.find_spec"


class TestAvailableExtras(unittest.TestCase):
    def test_real_call_returns_bool_map_without_raising(self) -> None:
        result = available_extras()
        assert isinstance(result, dict)
        assert set(result) == _EXPECTED_EXTRAS
        assert all(isinstance(v, bool) for v in result.values())

    def test_all_present(self) -> None:
        with patch(_FIND_SPEC, return_value=object()):
            result = available_extras()
        assert set(result) == _EXPECTED_EXTRAS
        assert all(result.values()), result
        # bundles derived from leaves must also be True
        assert result["llm"] is True
        assert result["vector"] is True
        assert result["all"] is True

    def test_all_missing(self) -> None:
        with patch(_FIND_SPEC, return_value=None):
            result = available_extras()
        assert set(result) == _EXPECTED_EXTRAS
        assert not any(result.values()), result
        assert result["all"] is False

    def test_find_spec_raising_is_treated_as_unavailable(self) -> None:
        with patch(_FIND_SPEC, side_effect=ModuleNotFoundError("no parent")):
            result = available_extras()
        # function returns normally; no exception escapes
        assert set(result) == _EXPECTED_EXTRAS
        assert not any(result.values()), result

    def test_partial_availability_bundles_require_all_leaves(self) -> None:
        def fake_find_spec(name: str) -> object | None:
            # only anthropic present; openai absent -> llm bundle must be False
            return object() if name == "anthropic" else None

        with patch(_FIND_SPEC, side_effect=fake_find_spec):
            result = available_extras()
        assert result["anthropic"] is True
        assert result["openai"] is False
        assert result["llm"] is False
        assert result["all"] is False


if __name__ == "__main__":
    unittest.main()
