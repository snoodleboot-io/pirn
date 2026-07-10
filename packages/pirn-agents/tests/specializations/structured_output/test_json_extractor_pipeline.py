"""Tests for :class:`JsonExtractorPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.structured_output.json_extractor_pipeline import (
    JsonExtractorPipeline,
)
from tests.specializations.conftest import (
    StubLLMProvider,
)


class TestJsonExtractorPipelineValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        knot = JsonExtractorPipeline.__new__(JsonExtractorPipeline)
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await knot.process(
                prompt="give me json",
                llm="not-a-provider",  # type: ignore[arg-type]
                schema={"name": "string"},
                max_retries=3,
            )

    async def test_rejects_zero_max_retries(self) -> None:
        llm = StubLLMProvider(['{"name": "x"}'])
        knot = JsonExtractorPipeline.__new__(JsonExtractorPipeline)
        with self.assertRaisesRegex(ValueError, "max_retries"):
            await knot.process(
                prompt="give me json",
                llm=llm,
                schema={"name": "string"},
                max_retries=0,
            )


class TestJsonExtractorPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
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
