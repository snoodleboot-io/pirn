"""Tests for :class:`ConfidenceRouter`."""

from __future__ import annotations

import pytest
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.routing.confidence_router import (
    ConfidenceRouter,
)
from pirn.tapestry import Tapestry


class TestConfidenceRouterProcess(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ConfidenceRouter:
        with Tapestry():
            return ConfidenceRouter(
                score=0.5,
                threshold=0.5,
                _config=KnotConfig(id="cr"),
            )

    async def test_returns_primary_when_above_threshold(self) -> None:
        knot = self._make()
        result = await knot.process(score=0.9, threshold=0.5)
        assert result == "primary"

    async def test_returns_primary_at_exact_threshold(self) -> None:
        knot = self._make()
        result = await knot.process(score=0.5, threshold=0.5)
        assert result == "primary"

    async def test_returns_fallback_when_below_threshold(self) -> None:
        knot = self._make()
        result = await knot.process(score=0.2, threshold=0.5)
        assert result == "fallback"

    async def test_rejects_non_numeric_score(self) -> None:
        knot = self._make()
        with self.assertRaisesRegex(TypeError, "score must be a float"):
            await knot.process(score="high", threshold=0.5)  # type: ignore[arg-type]

    async def test_rejects_non_numeric_threshold(self) -> None:
        knot = self._make()
        with self.assertRaisesRegex(TypeError, "threshold must be a float"):
            await knot.process(score=0.9, threshold="high")  # type: ignore[arg-type]
