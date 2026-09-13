"""Unit tests for :meth:`MemoryKindGuard.is_kind`."""

from __future__ import annotations

import unittest

from pirn_agents.memory.management.memory_kind_guard import MemoryKindGuard


class TestIsMemoryKind(unittest.TestCase):
    def test_accepts_every_valid_kind(self) -> None:
        for kind in ("episodic", "semantic", "procedural", "profile"):
            assert MemoryKindGuard.is_kind(kind)

    def test_rejects_unknown_string(self) -> None:
        assert not MemoryKindGuard.is_kind("working")

    def test_rejects_non_string(self) -> None:
        assert not MemoryKindGuard.is_kind(42)
        assert not MemoryKindGuard.is_kind(None)
