"""Tests for :class:`YamlExtractorPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.structured_output.yaml_extractor_pipeline import (
    YamlExtractorPipeline,
)
from pirn.tapestry import Tapestry

from tests.specializations.conftest import (
    StubLLMProvider,
)


def _make_knot(llm: StubLLMProvider, max_retries: int = 3) -> YamlExtractorPipeline:
    with Tapestry():
        return YamlExtractorPipeline(
            prompt="extract a user",
            llm=llm,
            schema={"name": "string", "age": "integer"},
            max_retries=max_retries,
            _config=KnotConfig(id="yaml"),
        )


class TestYamlExtractorPipelineProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["name: Ada\nage: 36\n"])
        knot = _make_knot(llm)
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await knot.process(
                prompt="give me yaml",
                llm="not-a-provider",  # type: ignore[arg-type]
                max_retries=3,
            )

    async def test_rejects_zero_max_retries(self) -> None:
        llm = StubLLMProvider(["name: Ada\nage: 36\n"])
        knot = _make_knot(llm)
        with self.assertRaisesRegex(ValueError, "max_retries"):
            await knot.process(
                prompt="give me yaml",
                llm=llm,
                max_retries=0,
            )

    async def test_returns_parsed_mapping(self) -> None:
        llm = StubLLMProvider(["name: Ada\nage: 36\n"])
        with Tapestry() as t:
            YamlExtractorPipeline(
                prompt="extract a user",
                llm=llm,
                schema={"name": "string", "age": "integer"},
                max_retries=3,
                _config=KnotConfig(id="yaml"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs["yaml"] == {"name": "Ada", "age": 36}

    async def test_retries_on_invalid_yaml(self) -> None:
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
        run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs["yaml"] == {"name": "Ada", "age": 36}
        assert len(llm.calls) == 2

    async def test_raises_after_exhausting_retries(self) -> None:
        llm = StubLLMProvider(["just a scalar"] * 5)
        knot = _make_knot(llm, max_retries=2)
        with self.assertRaisesRegex(ValueError, "exhausted"):
            await knot.process(
                prompt="extract a user",
                llm=llm,
                max_retries=2,
            )
