"""Unit tests for :class:`_JsonExtractorAttempt`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.structured_output._json_extractor_attempt import (
    _JsonExtractorAttempt,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestJsonExtractorAttemptProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_parsed_mapping_on_success(self) -> None:
        llm = StubLLMProvider(['{"name": "Alice", "age": 30}'])
        with Tapestry() as t:
            _JsonExtractorAttempt(
                prompt="extract person",
                llm=llm,
                schema={"name": "string", "age": "integer"},
                prior_error="",
                _config=KnotConfig(id="jea"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["jea"]
        assert out["name"] == "Alice"
        assert out["age"] == 30

    async def test_returns_error_string_on_invalid_json(self) -> None:
        llm = StubLLMProvider(["not valid json"])
        with Tapestry() as t:
            _JsonExtractorAttempt(
                prompt="extract",
                llm=llm,
                schema={"x": "str"},
                prior_error="",
                _config=KnotConfig(id="jea"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["jea"]
        assert isinstance(out, str)
        assert "invalid JSON" in out

    async def test_returns_error_string_on_missing_keys(self) -> None:
        llm = StubLLMProvider(['{"name": "Bob"}'])
        with Tapestry() as t:
            _JsonExtractorAttempt(
                prompt="extract",
                llm=llm,
                schema={"name": "str", "age": "int"},
                prior_error="",
                _config=KnotConfig(id="jea"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["jea"]
        assert isinstance(out, str)
        assert "missing" in out

    async def test_prior_error_included_in_system_prompt(self) -> None:
        llm = StubLLMProvider(['{"x": 1}'])
        with Tapestry() as t:
            _JsonExtractorAttempt(
                prompt="extract",
                llm=llm,
                schema={"x": "int"},
                prior_error="previous attempt gave invalid JSON",
                _config=KnotConfig(id="jea"),
            )
        await t.run(RunRequest())
        system_msg = llm.calls[0][0]["content"]
        assert "previous attempt failed" in system_msg


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_string_prompt(self) -> None:
        llm = StubLLMProvider(['{"x": 1}'])
        with Tapestry():
            k = _JsonExtractorAttempt.__new__(_JsonExtractorAttempt)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(prompt=42, llm=llm, schema={"x": "int"}, prior_error="")  # type: ignore[arg-type]
