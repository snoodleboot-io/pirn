"""Unit tests for :class:`EnumClassifierAttempt`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.structured_output._enum_classifier_attempt import (
    EnumClassifierAttempt,
)
from tests.specializations.conftest import StubLLMProvider


class TestEnumClassifierAttemptProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_matched_label(self) -> None:
        llm = StubLLMProvider(["positive"])
        with Tapestry() as t:
            EnumClassifierAttempt(
                prompt="Is this good?",
                llm=llm,
                labels=["positive", "negative", "neutral"],
                _config=KnotConfig(id="eca"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["eca"] == "positive"

    async def test_case_insensitive_match(self) -> None:
        llm = StubLLMProvider(["POSITIVE"])
        with Tapestry() as t:
            EnumClassifierAttempt(
                prompt="classify",
                llm=llm,
                labels=["positive", "negative"],
                _config=KnotConfig(id="eca"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["eca"] == "positive"

    async def test_raises_when_no_label_matches(self) -> None:
        llm = StubLLMProvider(["unknown_label"])
        with Tapestry() as t:
            EnumClassifierAttempt(
                prompt="classify",
                llm=llm,
                labels=["positive", "negative"],
                _config=KnotConfig(id="eca"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_non_string_prompt(self) -> None:
        llm = StubLLMProvider(["positive"])
        with Tapestry():
            knot = EnumClassifierAttempt(
                prompt="p", llm=llm, labels=["positive"], _config=KnotConfig(id="eca2")
            )
        result = await knot({"prompt": 42, "llm": llm, "labels": ["positive"]})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_string_prompt(self) -> None:
        llm = StubLLMProvider(["positive"])
        with Tapestry():
            k = EnumClassifierAttempt(
                prompt="p", llm=llm, labels=["positive", "negative"], _config=KnotConfig(id="x")
            )
        result = await k({"prompt": 42, "llm": llm, "labels": ["positive", "negative"]})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"
