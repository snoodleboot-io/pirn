"""Unit tests for :class:`_EnumClassifierAttempt`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.structured_output._enum_classifier_attempt import (
    _EnumClassifierAttempt,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestEnumClassifierAttemptProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_matched_label(self) -> None:
        llm = StubLLMProvider(["positive"])
        with Tapestry() as t:
            _EnumClassifierAttempt(
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
            _EnumClassifierAttempt(
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
            _EnumClassifierAttempt(
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
            with self.assertRaises(TypeError):
                _EnumClassifierAttempt(
                    prompt=42,  # type: ignore[arg-type]
                    llm=llm,
                    labels=["positive"],
                    _config=KnotConfig(id="eca"),
                )
