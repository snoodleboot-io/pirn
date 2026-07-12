"""Tests for :class:`SentenceConfidenceMonitor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.sentence_confidence_monitor import SentenceConfidenceMonitor


def _monitor() -> SentenceConfidenceMonitor:
    with Tapestry():
        knot = SentenceConfidenceMonitor.__new__(SentenceConfidenceMonitor)
        object.__setattr__(knot, "_config", KnotConfig(id="monitor"))
    return knot


class TestSentenceConfidenceMonitor(unittest.IsolatedAsyncioTestCase):
    async def test_flags_low_confidence(self) -> None:
        assert await _monitor().process(sentence="s", confidence=0.2, threshold=0.5) is True

    async def test_passes_high_confidence(self) -> None:
        assert await _monitor().process(sentence="s", confidence=0.8, threshold=0.5) is False

    async def test_boundary_is_not_flagged(self) -> None:
        assert await _monitor().process(sentence="s", confidence=0.5, threshold=0.5) is False

    async def test_static_rule(self) -> None:
        assert SentenceConfidenceMonitor.needs_retrieval(0.1, 0.5) is True
        assert SentenceConfidenceMonitor.needs_retrieval(0.9, 0.5) is False

    async def test_rejects_out_of_range_confidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "confidence must be in"):
            await _monitor().process(sentence="s", confidence=1.5, threshold=0.5)
