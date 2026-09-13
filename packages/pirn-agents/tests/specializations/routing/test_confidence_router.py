"""Tests for :class:`ConfidenceRouter`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.routing.confidence_router import (
    ConfidenceRouter,
)


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
        result = await knot({"score": "high", "threshold": 0.5})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_rejects_non_numeric_threshold(self) -> None:
        knot = self._make()
        result = await knot({"score": 0.9, "threshold": "high"})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"
