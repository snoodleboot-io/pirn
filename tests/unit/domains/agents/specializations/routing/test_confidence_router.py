"""Tests for :class:`ConfidenceRouter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.routing.confidence_router import (
    ConfidenceRouter,
)
from pirn.tapestry import Tapestry


@pytest.mark.asyncio
class TestConfidenceRouterConstruction:
    async def test_rejects_non_numeric_threshold(self) -> None:
        with pytest.raises(TypeError, match="threshold must be a float"):
            with Tapestry():
                ConfidenceRouter(
                    score=0.9,
                    threshold="high",  # type: ignore[arg-type]
                    _config=KnotConfig(id="cr"),
                )


@pytest.mark.asyncio
class TestConfidenceRouterProcess:
    async def test_returns_primary_when_above_threshold(self) -> None:
        with Tapestry() as t:
            ConfidenceRouter(
                score=0.9,
                threshold=0.5,
                _config=KnotConfig(id="cr"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["cr"] == "primary"

    async def test_returns_primary_at_exact_threshold(self) -> None:
        with Tapestry() as t:
            ConfidenceRouter(
                score=0.5,
                threshold=0.5,
                _config=KnotConfig(id="cr"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["cr"] == "primary"

    async def test_returns_fallback_when_below_threshold(self) -> None:
        with Tapestry() as t:
            ConfidenceRouter(
                score=0.2,
                threshold=0.5,
                _config=KnotConfig(id="cr"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["cr"] == "fallback"

    async def test_rejects_non_numeric_score(self) -> None:
        with pytest.raises(TypeError):
            with Tapestry():
                ConfidenceRouter(
                    score="high",  # type: ignore[arg-type]
                    threshold=0.5,
                    _config=KnotConfig(id="cr"),
                )
