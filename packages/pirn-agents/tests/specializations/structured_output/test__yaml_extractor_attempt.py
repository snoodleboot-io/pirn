"""Unit tests for :class:`_YamlExtractorAttempt`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.structured_output._yaml_extractor_attempt import (
    _YamlExtractorAttempt,
)
from pirn.tapestry import Tapestry

from tests.specializations.conftest import StubLLMProvider


class TestYamlExtractorAttemptProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_parsed_mapping_on_success(self) -> None:
        llm = StubLLMProvider(["name: Alice\nage: 30"])
        with Tapestry() as t:
            _YamlExtractorAttempt(
                prompt="extract person",
                llm=llm,
                schema={"name": "str", "age": "int"},
                prior_error="",
                _config=KnotConfig(id="yea"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["yea"]
        assert out["name"] == "Alice"
        assert out["age"] == 30

    async def test_returns_error_string_on_invalid_yaml(self) -> None:
        llm = StubLLMProvider(["key: :\n  broken:"])
        with Tapestry() as t:
            _YamlExtractorAttempt(
                prompt="extract",
                llm=llm,
                schema=None,
                prior_error="",
                _config=KnotConfig(id="yea"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["yea"]
        assert isinstance(out, str)

    async def test_returns_error_on_missing_schema_keys(self) -> None:
        llm = StubLLMProvider(["name: Bob"])
        with Tapestry() as t:
            _YamlExtractorAttempt(
                prompt="extract",
                llm=llm,
                schema={"name": "str", "age": "int"},
                prior_error="",
                _config=KnotConfig(id="yea"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["yea"]
        assert isinstance(out, str)
        assert "missing" in out

    async def test_rejects_non_string_prompt(self) -> None:
        llm = StubLLMProvider(["x: 1"])
        knot = _YamlExtractorAttempt.__new__(_YamlExtractorAttempt)
        with self.assertRaises(TypeError):
            await knot.process(
                prompt=42,  # type: ignore[arg-type]
                llm=llm,
                schema=None,
                prior_error="",
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_string_prompt(self) -> None:
        llm = StubLLMProvider(["x: 1"])
        with Tapestry():
            k = _YamlExtractorAttempt.__new__(_YamlExtractorAttempt)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(prompt=99, llm=llm, schema=None, prior_error="")  # type: ignore[arg-type]
