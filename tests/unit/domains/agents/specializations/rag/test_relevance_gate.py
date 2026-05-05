"""Unit tests for :class:`RelevanceGate`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.rag.relevance_gate import RelevanceGate
from pirn.tapestry import Tapestry


class _DocsSource(Knot):
    def __init__(self, docs, *, _config, **kwargs):
        self._docs = docs
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any):
        return self._docs


class TestRelevanceGateConstruction(unittest.TestCase):
    def test_rejects_out_of_range_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, "threshold"):
            with Tapestry():
                src = _DocsSource([], _config=KnotConfig(id="src"))
                RelevanceGate(
                    query="q",
                    retrieved=src,
                    threshold=1.5,
                    _config=KnotConfig(id="rg"),
                )


class TestRelevanceGateProcess(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_relevant_docs(self) -> None:
        docs = [{"text": "python programming language"}]
        with Tapestry() as t:
            src = _DocsSource(docs, _config=KnotConfig(id="src"))
            RelevanceGate(
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
            RelevanceGate(
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
            RelevanceGate(
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

    async def test_rejects_non_string_query(self) -> None:
        with Tapestry():
            src = _DocsSource([], _config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                RelevanceGate(
                    query=42,  # type: ignore[arg-type]
                    retrieved=src,
                    threshold=0.5,
                    _config=KnotConfig(id="rg"),
                )
