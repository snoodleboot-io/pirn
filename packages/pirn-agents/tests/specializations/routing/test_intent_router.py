"""Tests for :class:`IntentRouter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.routing.intent_router import (
    IntentRouter,
)
from tests.specializations.conftest import StubLLMProvider


class TestIntentRouterProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, llm: StubLLMProvider) -> IntentRouter:
        with Tapestry():
            return IntentRouter(
                message="hello",
                llm=llm,
                categories=["a", "b"],
                _config=KnotConfig(id="ir"),
            )

    async def test_returns_matching_category(self) -> None:
        llm = StubLLMProvider(["billing"])
        knot = self._make_knot(llm)
        result = await knot.process(
            message="I have a question about my invoice",
            llm=llm,
            categories=["billing", "support", "general"],
        )
        assert result == "billing"

    async def test_falls_back_to_first_category_on_unrecognised_label(self) -> None:
        llm = StubLLMProvider(["unknown_label"])
        knot = self._make_knot(llm)
        result = await knot.process(
            message="some message",
            llm=llm,
            categories=["alpha", "beta"],
        )
        assert result == "alpha"

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["a"])
        knot = self._make_knot(llm)
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await knot.process(
                message="hello",
                llm="not-a-provider",  # type: ignore[arg-type]
                categories=["a", "b"],
            )

    async def test_rejects_empty_categories(self) -> None:
        llm = StubLLMProvider(["a"])
        knot = self._make_knot(llm)
        with self.assertRaisesRegex(ValueError, "categories must be a non-empty"):
            await knot.process(message="hello", llm=llm, categories=[])

    async def test_rejects_non_string_message(self) -> None:
        llm = StubLLMProvider(["alpha"])
        knot = self._make_knot(llm)
        with self.assertRaises(TypeError):
            await knot.process(
                message=99,  # type: ignore[arg-type]
                llm=llm,
                categories=["alpha"],
            )
