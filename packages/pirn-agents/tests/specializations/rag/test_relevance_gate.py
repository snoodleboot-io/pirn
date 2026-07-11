"""Unit tests for :class:`RelevanceCheck`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.relevance_gate import RelevanceCheck


class _DocsSource(Knot):
    def __init__(self, docs, *, _config, **kwargs):
        self._docs = docs
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any):
        return self._docs


class TestRelevanceCheckProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_out_of_range_threshold(self) -> None:
        knot = RelevanceCheck(
            query="q",
            retrieved=_DocsSource([], _config=KnotConfig(id="src")),
            _config=KnotConfig(id="rg"),
        )
        with self.assertRaisesRegex(ValueError, "threshold"):
            await knot.process(query="q", retrieved=[], threshold=1.5)

    async def test_rejects_non_string_query(self) -> None:
        knot = RelevanceCheck(
            query="q",
            retrieved=_DocsSource([], _config=KnotConfig(id="src")),
            _config=KnotConfig(id="rg"),
        )
        with self.assertRaises(TypeError):
            await knot.process(query=42, retrieved=[], threshold=0.5)  # type: ignore[arg-type]

    async def test_keeps_relevant_docs(self) -> None:
        docs = [{"text": "python programming language"}]
        with Tapestry() as t:
            src = _DocsSource(docs, _config=KnotConfig(id="src"))
            RelevanceCheck(
                query="python",
                retrieved=src,
                threshold=0.1,
                _config=KnotConfig(id="rg"),
            )
        result = await t.run(RunRequest())
        assert len(result.outputs["rg"]) == 1

    async def test_filters_irrelevant_docs(self) -> None:
        docs = [{"text": "completely unrelated topic"}]
        with Tapestry() as t:
            src = _DocsSource(docs, _config=KnotConfig(id="src"))
            RelevanceCheck(
                query="python programming",
                retrieved=src,
                threshold=0.9,  # very high bar
                _config=KnotConfig(id="rg"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["rg"] == []

    async def test_custom_scorer_used(self) -> None:
        docs = [{"text": "x"}, {"text": "y"}]
        # Always score 1.0 for first doc, 0.0 for second
        call_count = [0]

        def scorer(query, doc):
            call_count[0] += 1
            return 1.0 if doc.get("text") == "x" else 0.0

        with Tapestry() as t:
            src = _DocsSource(docs, _config=KnotConfig(id="src"))
            RelevanceCheck(
                query="q",
                retrieved=src,
                threshold=0.5,
                scorer=scorer,
                _config=KnotConfig(id="rg"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["rg"]
        assert len(out) == 1
        assert out[0]["text"] == "x"
