"""Unit tests for :class:`RetryOnParseFailure`."""

from __future__ import annotations

import json
from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.structured_output.retry_on_parse_failure import (
    RetryOnParseFailure,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestRetryOnParseFailureConstruction(unittest.TestCase):
    def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                RetryOnParseFailure(
                    prompt="p",
                    llm="bad",  # type: ignore[arg-type]
                    parser=json.loads,
                    _config=KnotConfig(id="ropf"),
                )

    def test_rejects_non_callable_parser(self) -> None:
        with self.assertRaisesRegex(TypeError, "parser"):
            with Tapestry():
                RetryOnParseFailure(
                    prompt="p",
                    llm=StubLLMProvider([]),
                    parser="not-callable",  # type: ignore[arg-type]
                    _config=KnotConfig(id="ropf"),
                )

    def test_rejects_non_positive_max_retries(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_retries"):
            with Tapestry():
                RetryOnParseFailure(
                    prompt="p",
                    llm=StubLLMProvider([]),
                    parser=json.loads,
                    max_retries=0,
                    _config=KnotConfig(id="ropf"),
                )


class TestRetryOnParseFailureProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_parsed_on_first_success(self) -> None:
        llm = StubLLMProvider(['{"x": 1}'])
        with Tapestry() as t:
            RetryOnParseFailure(
                prompt="extract JSON",
                llm=llm,
                parser=json.loads,
                max_retries=3,
                _config=KnotConfig(id="ropf"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ropf"] == {"x": 1}

    async def test_retries_on_parse_failure_and_succeeds(self) -> None:
        llm = StubLLMProvider(["not json", '{"x": 2}'])
        with Tapestry() as t:
            RetryOnParseFailure(
                prompt="extract JSON",
                llm=llm,
                parser=json.loads,
                max_retries=3,
                _config=KnotConfig(id="ropf"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ropf"] == {"x": 2}

    async def test_raises_after_exhausting_retries(self) -> None:
        llm = StubLLMProvider(["bad json"] * 5)
        with Tapestry() as t:
            RetryOnParseFailure(
                prompt="extract JSON",
                llm=llm,
                parser=json.loads,
                max_retries=2,
                _config=KnotConfig(id="ropf"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_non_string_prompt(self) -> None:
        llm = StubLLMProvider(["{}"])
        with Tapestry():
            with self.assertRaises(TypeError):
                RetryOnParseFailure(
                    prompt=42,  # type: ignore[arg-type]
                    llm=llm,
                    parser=json.loads,
                    _config=KnotConfig(id="ropf"),
                )
