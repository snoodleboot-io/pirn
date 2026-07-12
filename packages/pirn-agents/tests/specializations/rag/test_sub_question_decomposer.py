"""Tests for :class:`SubQuestionDecomposer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.sub_question_decomposer import SubQuestionDecomposer
from tests.specializations.conftest import StubLLMProvider


def _decomposer() -> SubQuestionDecomposer:
    with Tapestry():
        knot = SubQuestionDecomposer.__new__(SubQuestionDecomposer)
        object.__setattr__(knot, "_config", KnotConfig(id="decompose"))
    return knot


class TestSubQuestionDecomposer(unittest.IsolatedAsyncioTestCase):
    async def test_splits_into_sub_questions(self) -> None:
        llm = StubLLMProvider(["What is X?\nWhat is Y?\nHow do X and Y compare?"])
        knot = _decomposer()
        subs = await knot.process(query="Compare X and Y", llm=llm, max_sub_questions=4)
        assert subs == ["What is X?", "What is Y?", "How do X and Y compare?"]

    async def test_caps_at_max(self) -> None:
        llm = StubLLMProvider(["a\nb\nc\nd\ne"])
        knot = _decomposer()
        subs = await knot.process(query="q", llm=llm, max_sub_questions=2)
        assert subs == ["a", "b"]

    async def test_empty_falls_back_to_query(self) -> None:
        llm = StubLLMProvider([""])
        knot = _decomposer()
        subs = await knot.process(query="fallback", llm=llm, max_sub_questions=3)
        assert subs == ["fallback"]

    async def test_rejects_non_positive_max(self) -> None:
        knot = _decomposer()
        with self.assertRaisesRegex(ValueError, "max_sub_questions must be a positive int"):
            await knot.process(query="q", llm=StubLLMProvider(["x"]), max_sub_questions=0)
