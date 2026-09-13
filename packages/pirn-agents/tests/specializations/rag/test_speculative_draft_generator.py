"""Tests for :class:`SpeculativeDraftGenerator`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.speculative_draft_generator import SpeculativeDraftGenerator
from tests.specializations.conftest import StubLLMProvider


def _generator() -> SpeculativeDraftGenerator:
    with Tapestry():
        knot = SpeculativeDraftGenerator(
            query="q", llm=StubLLMProvider(["x"]), _config=KnotConfig(id="draft")
        )
    return knot


class TestSpeculativeDraftGenerator(unittest.IsolatedAsyncioTestCase):
    async def test_drafts_without_retrieval(self) -> None:
        llm = StubLLMProvider(["a quick draft"])
        knot = _generator()
        draft = await knot.process(query="what is X?", llm=llm)
        assert draft == "a quick draft"
        # Exactly one LLM call, no sources in the prompt.
        assert len(llm.calls) == 1

    async def test_rejects_non_string_query(self) -> None:
        knot = _generator()
        result = await knot({"query": 1, "llm": StubLLMProvider(["x"])})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"
