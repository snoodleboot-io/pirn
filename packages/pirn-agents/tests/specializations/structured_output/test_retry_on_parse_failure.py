"""Unit tests for :class:`RetryOnParseFailure`."""

from __future__ import annotations

import json
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.structured_output.retry_on_parse_failure import (
    RetryOnParseFailure,
)
from tests.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider, max_retries: int = 3) -> RetryOnParseFailure:
    with Tapestry():
        return RetryOnParseFailure(
            prompt="extract JSON",
            llm=llm,
            parser=json.loads,
            max_retries=max_retries,
            _config=KnotConfig(id="ropf"),
        )


class TestRetryOnParseFailureProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider([])
        knot = _make_knot(llm)
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            await knot.process(
                prompt="p",
                llm="bad",  # type: ignore[arg-type]
                parser=json.loads,
                max_retries=3,
            )

    async def test_rejects_non_callable_parser(self) -> None:
        llm = StubLLMProvider([])
        knot = _make_knot(llm)
        with self.assertRaisesRegex(TypeError, "parser"):
            await knot.process(
                prompt="p",
                llm=llm,
                parser="not-callable",  # type: ignore[arg-type]
                max_retries=3,
            )

    async def test_rejects_non_positive_max_retries(self) -> None:
        llm = StubLLMProvider([])
        knot = _make_knot(llm)
        with self.assertRaisesRegex(ValueError, "max_retries"):
            await knot.process(
                prompt="p",
                llm=llm,
                parser=json.loads,
                max_retries=0,
            )

    async def test_rejects_non_string_prompt(self) -> None:
        llm = StubLLMProvider(["{}"])
        knot = _make_knot(llm)
        with self.assertRaises(TypeError):
            await knot.process(
                prompt=42,  # type: ignore[arg-type]
                llm=llm,
                parser=json.loads,
                max_retries=3,
            )

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
        run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs["ropf"] == {"x": 1}

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
        run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs["ropf"] == {"x": 2}

    async def test_raises_after_exhausting_retries(self) -> None:
        # `process()` now returns a loop knot rather than running the retries
        # itself (ADR agents-speaks-core WS5a) — the exhaustion raise happens
        # inside `RetryResultExtractor`, reached only through a real engine
        # run, so this asserts on the run's recorded failure rather than a
        # bare synchronous ValueError from `process()`. The outer run only
        # sees a generic SubTapestryError; the real ValueError is recorded on
        # the *inner* run (ropf's own inner tapestry), reachable via the
        # outer lineage row's `inner_run_id`.
        llm = StubLLMProvider(["bad json"] * 5)
        with Tapestry() as t:
            RetryOnParseFailure(
                prompt="extract JSON",
                llm=llm,
                parser=json.loads,
                max_retries=2,
                _config=KnotConfig(id="ropf"),
            )
        run = await t.run(RunRequest())
        assert not run.succeeded
        assert "ropf" not in run.outputs

        outer_record = next(row for row in run.lineage if row.knot_id == "ropf")
        inner_run = await t.history.get_run(outer_record.extra["inner_run_id"])
        assert not inner_run.succeeded
        assert any(
            exc.exc_type == "ValueError" and "exhausted" in exc.message
            for exc in inner_run.exceptions
        )
