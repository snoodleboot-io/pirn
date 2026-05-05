"""Tests for :class:`IntentRouter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.routing.intent_router import (
    IntentRouter,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestIntentRouterConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            with Tapestry():
                IntentRouter(
                    message="hello",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    categories=["a", "b"],
                    _config=KnotConfig(id="ir"),
                )

    async def test_rejects_empty_categories(self) -> None:
        llm = StubLLMProvider(["a"])
        with self.assertRaisesRegex(ValueError, "categories must be a non-empty"):
            with Tapestry():
                IntentRouter(
                    message="hello",
                    llm=llm,
                    categories=[],
                    _config=KnotConfig(id="ir"),
                )


class TestIntentRouterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_matching_category(self) -> None:
        llm = StubLLMProvider(["billing"])
        with Tapestry() as t:
            IntentRouter(
                message="I have a question about my invoice",
                llm=llm,
                categories=["billing", "support", "general"],
                _config=KnotConfig(id="ir"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["ir"] == "billing"

    async def test_falls_back_to_first_category_on_unrecognised_label(self,) -> None:
        llm = StubLLMProvider(["unknown_label"])
        with Tapestry() as t:
            IntentRouter(
                message="some message",
                llm=llm,
                categories=["alpha", "beta"],
                _config=KnotConfig(id="ir"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["ir"] == "alpha"

    async def test_rejects_non_string_message(self) -> None:
        llm = StubLLMProvider(["alpha"])
        with self.assertRaises(TypeError):
            with Tapestry():
                IntentRouter(
                    message=99,  # type: ignore[arg-type]
                    llm=llm,
                    categories=["alpha"],
                    _config=KnotConfig(id="ir"),
                )
