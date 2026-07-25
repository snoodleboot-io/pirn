"""Unit tests for :func:`is_memory_kind`."""

from __future__ import annotations

import unittest

from pirn_agents.memory_management.memory_kind import is_memory_kind


class TestIsMemoryKind(unittest.TestCase):
    def test_accepts_every_valid_kind(self) -> None:
        for kind in ("episodic", "semantic", "procedural", "profile"):
            assert is_memory_kind(kind)

    def test_rejects_unknown_string(self) -> None:
        assert not is_memory_kind("working")

    def test_rejects_non_string(self) -> None:
        assert not is_memory_kind(42)
        assert not is_memory_kind(None)
