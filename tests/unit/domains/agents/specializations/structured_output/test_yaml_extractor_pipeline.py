"""Tests for :class:`YamlExtractorPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.structured_output.yaml_extractor_pipeline import (  # noqa: E501
    YamlExtractorPipeline,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
)


@pytest.mark.asyncio
class TestYamlExtractorPipelineConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                YamlExtractorPipeline(
                    prompt="give me yaml",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="yaml"),
                )

    async def test_rejects_zero_max_retries(self) -> None:
        llm = StubLLMProvider(["name: Ada\nage: 36\n"])
        with pytest.raises(ValueError, match="max_retries"):
            with Tapestry():
                YamlExtractorPipeline(
                    prompt="give me yaml",
                    llm=llm,
                    max_retries=0,
                    _config=KnotConfig(id="yaml"),
                )


@pytest.mark.asyncio
class TestYamlExtractorPipelineHappyPath:
    async def test_returns_parsed_mapping(self) -> None:
        llm = StubLLMProvider(["name: Ada\nage: 36\n"])
        with Tapestry() as t:
            YamlExtractorPipeline(
                prompt="extract a user",
                llm=llm,
                schema={"name": "string", "age": "integer"},
                _config=KnotConfig(id="yaml"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        parsed = result.outputs["yaml"]
        assert parsed == {"name": "Ada", "age": 36}

    async def test_retries_on_invalid_yaml(self) -> None:
        # First reply is a YAML scalar, not a mapping — pipeline should retry.
        llm = StubLLMProvider(
            [
                "just a scalar string",
                "name: Ada\nage: 36\n",
            ]
        )
        with Tapestry() as t:
            YamlExtractorPipeline(
                prompt="extract a user",
                llm=llm,
                schema={"name": "string"},
                max_retries=3,
                _config=KnotConfig(id="yaml"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        parsed = result.outputs["yaml"]
        assert parsed == {"name": "Ada", "age": 36}
        assert len(llm.calls) == 2
