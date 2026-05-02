"""Tests for :class:`JsonExtractorPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.structured_output.json_extractor_pipeline import (  # noqa: E501
    JsonExtractorPipeline,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
)


@pytest.mark.asyncio
class TestJsonExtractorPipelineConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                JsonExtractorPipeline(
                    prompt="give me json",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    schema={"name": "string"},
                    _config=KnotConfig(id="json"),
                )

    async def test_rejects_zero_max_retries(self) -> None:
        llm = StubLLMProvider(['{"name": "x"}'])
        with pytest.raises(ValueError, match="max_retries"):
            with Tapestry():
                JsonExtractorPipeline(
                    prompt="give me json",
                    llm=llm,
                    schema={"name": "string"},
                    max_retries=0,
                    _config=KnotConfig(id="json"),
                )


@pytest.mark.asyncio
class TestJsonExtractorPipelineHappyPath:
    async def test_returns_parsed_dict_on_first_attempt(self) -> None:
        llm = StubLLMProvider(['{"name": "Ada", "age": 36}'])
        with Tapestry() as t:
            JsonExtractorPipeline(
                prompt="extract user record",
                llm=llm,
                schema={"name": "string", "age": "integer"},
                _config=KnotConfig(id="json"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        parsed = result.outputs["json"]
        assert parsed == {"name": "Ada", "age": 36}

    async def test_retries_on_invalid_json(self) -> None:
        llm = StubLLMProvider(
            [
                "not json at all",
                '{"name": "Ada", "age": 36}',
            ]
        )
        with Tapestry() as t:
            JsonExtractorPipeline(
                prompt="extract user record",
                llm=llm,
                schema={"name": "string", "age": "integer"},
                max_retries=3,
                _config=KnotConfig(id="json"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        parsed = result.outputs["json"]
        assert parsed == {"name": "Ada", "age": 36}
        assert len(llm.calls) == 2
