"""Tests for :class:`EnumClassifierPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.structured_output.enum_classifier_pipeline import (  # noqa: E501
    EnumClassifierPipeline,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
)


class TestEnumClassifierPipelineConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_labels(self) -> None:
        llm = StubLLMProvider(["positive"])
        with self.assertRaisesRegex(ValueError, "labels must be a non-empty"):
            with Tapestry():
                EnumClassifierPipeline(
                    prompt="classify",
                    llm=llm,
                    labels=(),
                    _config=KnotConfig(id="classify"),
                )

    async def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            with Tapestry():
                EnumClassifierPipeline(
                    prompt="classify",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    labels=("a", "b"),
                    _config=KnotConfig(id="classify"),
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
