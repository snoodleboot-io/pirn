"""Tests for :class:`EnumClassifierPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.structured_output.enum_classifier_pipeline import (
    EnumClassifierPipeline,
)
from tests.specializations.conftest import (
    StubLLMProvider,
)


class TestEnumClassifierPipelineValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_labels(self) -> None:
        llm = StubLLMProvider(["positive"])
        knot = EnumClassifierPipeline.__new__(EnumClassifierPipeline)
        with self.assertRaisesRegex(ValueError, "labels must be a non-empty"):
            await knot.process(prompt="classify", llm=llm, labels=())

    async def test_rejects_non_llm_provider(self) -> None:
        knot = EnumClassifierPipeline.__new__(EnumClassifierPipeline)
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await knot.process(
                prompt="classify",
                llm="not-a-provider",  # type: ignore[arg-type]
                labels=("a", "b"),
            )


class TestEnumClassifierPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_matched_label(self) -> None:
        llm = StubLLMProvider(["positive"])
        with Tapestry() as t:
            EnumClassifierPipeline(
                prompt="The product is wonderful.",
                llm=llm,
                labels=("positive", "negative", "neutral"),
                _config=KnotConfig(id="classify"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["classify"] == "positive"

    async def test_matches_case_insensitively(self) -> None:
        llm = StubLLMProvider(["NEGATIVE"])
        with Tapestry() as t:
            EnumClassifierPipeline(
                prompt="The product is awful.",
                llm=llm,
                labels=("positive", "negative"),
                _config=KnotConfig(id="classify"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["classify"] == "negative"
