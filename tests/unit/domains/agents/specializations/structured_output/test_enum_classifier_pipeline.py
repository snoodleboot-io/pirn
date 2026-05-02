"""Tests for :class:`EnumClassifierPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.structured_output.enum_classifier_pipeline import (  # noqa: E501
    EnumClassifierPipeline,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
)


@pytest.mark.asyncio
class TestEnumClassifierPipelineConstruction:
    async def test_rejects_empty_labels(self) -> None:
        llm = StubLLMProvider(["positive"])
        with pytest.raises(ValueError, match="labels must be a non-empty"):
            with Tapestry():
                EnumClassifierPipeline(
                    prompt="classify",
                    llm=llm,
                    labels=(),
                    _config=KnotConfig(id="classify"),
                )

    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                EnumClassifierPipeline(
                    prompt="classify",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    labels=("a", "b"),
                    _config=KnotConfig(id="classify"),
                )


@pytest.mark.asyncio
class TestEnumClassifierPipelineHappyPath:
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
