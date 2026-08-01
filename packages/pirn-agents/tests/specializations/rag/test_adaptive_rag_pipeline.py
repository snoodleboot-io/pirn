"""Tests for :class:`AdaptiveRAGPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.adaptive_rag_pipeline import (
    AdaptiveRAGPipeline,
    _select_complexity_route,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
)


class TestAdaptiveRAGPipelineSimple(unittest.IsolatedAsyncioTestCase):
    async def test_routes_simple_to_direct_llm(self) -> None:
        memory = StubMemoryStore([{"text": "irrelevant"}])
        llm = StubLLMProvider(["SIMPLE", "direct answer"])
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="What color is the sky?",
                memory=memory,
                llm=llm,
                _config=KnotConfig(id="adaptive"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["adaptive"]
        assert isinstance(response, AgentResponse)
        assert response.content == "direct answer"
        assert memory.search_queries == []


class TestAdaptiveRAGPipelineModerate(unittest.IsolatedAsyncioTestCase):
    async def test_routes_moderate_to_naive_rag(self) -> None:
        memory = StubMemoryStore([{"text": "some context"}])
        llm = StubLLMProvider(["MODERATE", "rag answer"])
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="Tell me about photosynthesis",
                memory=memory,
                llm=llm,
                top_k=1,
                _config=KnotConfig(id="adaptive"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["adaptive"]
        assert isinstance(response, AgentResponse)
        assert response.content == "rag answer"
        assert len(memory.search_queries) == 1


class TestAdaptiveRAGPipelineComplex(unittest.IsolatedAsyncioTestCase):
    async def test_routes_complex_to_multi_hop(self) -> None:
        memory = StubMemoryStore([{"text": "hop context"}])
        llm = StubLLMProvider(["COMPLEX", "sub-q1\nsub-q2\nsub-q3", "multi-hop answer"])
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="Complex multi-part question",
                memory=memory,
                llm=llm,
                top_k=1,
                _config=KnotConfig(id="adaptive"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["adaptive"]
        assert isinstance(response, AgentResponse)
        assert response.content == "multi-hop answer"
        assert len(memory.search_queries) == 3


class TestAdaptiveRAGPipelineHedgedClassification(unittest.IsolatedAsyncioTestCase):
    """A classifier reply naming two labels must route to the one it means.

    Both label tests are substring matches. Before PIR-770 SIMPLE was tried
    first, so a reply like ``"COMPLEX (not simple)"`` took the SIMPLE arm —
    and because that arm answers directly with the next LLM response, the run
    returned the *sub-question decomposition* as the answer, with
    ``succeeded=True`` and no exception. A silent wrong answer.
    """

    async def test_complex_reply_mentioning_simple_routes_to_multi_hop(self) -> None:
        memory = StubMemoryStore([{"text": "hop context"}])
        llm = StubLLMProvider(
            ["COMPLEX (not simple)", "sub-q1\nsub-q2\nsub-q3", "multi-hop answer"]
        )
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="Complex multi-part question",
                memory=memory,
                llm=llm,
                top_k=1,
                _config=KnotConfig(id="adaptive"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["adaptive"]
        assert isinstance(response, AgentResponse)
        assert response.content == "multi-hop answer"
        assert len(memory.search_queries) == 3

    async def test_bare_simple_reply_still_routes_to_direct_llm(self) -> None:
        """The fix must not cost the well-behaved reply its arm."""
        memory = StubMemoryStore([{"text": "irrelevant"}])
        llm = StubLLMProvider(["SIMPLE", "direct answer"])
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="What color is the sky?",
                memory=memory,
                llm=llm,
                _config=KnotConfig(id="adaptive"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["adaptive"]
        assert isinstance(response, AgentResponse)
        assert response.content == "direct answer"
        assert memory.search_queries == []


class TestSelectComplexityRoute(unittest.TestCase):
    """Direct coverage of the selector, which sees an upper-cased reply."""

    def test_exact_labels(self) -> None:
        assert _select_complexity_route("SIMPLE") == "simple"
        assert _select_complexity_route("MODERATE") == "moderate"
        assert _select_complexity_route("COMPLEX") == "complex"

    def test_exact_match_wins_over_substring_ordering(self) -> None:
        assert _select_complexity_route("SIMPLE") == "simple"

    def test_padded_single_label(self) -> None:
        assert _select_complexity_route("THE ANSWER IS COMPLEX.") == "complex"
        assert _select_complexity_route("THIS ONE IS SIMPLE.") == "simple"

    def test_hedged_reply_naming_both_labels_resolves_to_complex(self) -> None:
        """A reply naming both labels is irreducibly ambiguous — COMPLEX wins.

        Substring matching cannot tell ``"COMPLEX (not simple)"`` from
        ``"SIMPLE, not complex"``; nor can whole-word matching. Some tiebreak
        has to be picked, and COMPLEX is picked deliberately: routing a simple
        query through multi-hop costs latency and tokens, whereas routing a
        complex query to the direct arm returns a wrong answer. This is the
        recorded decision, not an accident of ordering — see PIR-770.
        """
        assert _select_complexity_route("COMPLEX (NOT SIMPLE)") == "complex"
        assert _select_complexity_route("SIMPLE, NOT COMPLEX") == "complex"

    def test_unrecognised_reply_falls_back_to_moderate(self) -> None:
        assert _select_complexity_route("") == "moderate"
        assert _select_complexity_route("BANANA") == "moderate"


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_string_query(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["SIMPLE", "answer"])
        with Tapestry():
            k = AdaptiveRAGPipeline.__new__(AdaptiveRAGPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        # Tightened by PIR-715. The docstring has always promised TypeError, but
        # the guard was missing, so this actually raised AttributeError
        # ('_mutable_outer_history') from sub_tapestry.py — and the assertion
        # accepted either, hiding the gap.
        with self.assertRaisesRegex(TypeError, "query must be a string"):
            await k.process(query=123, memory=memory, llm=llm, top_k=5)  # type: ignore[arg-type]


class TestAdaptiveRAGPipelineArmObservability(unittest.IsolatedAsyncioTestCase):
    """The selected arm's knots must belong to the run this pipeline reports.

    Each arm used to open its own `with Tapestry()`, run it via `_run_inner`,
    pull the answer out, and return a `_ResultSource` closure wrapping the
    precomputed value. The pipeline's own inner run therefore contained exactly
    one knot — that closure — on every path, whatever work the arm had done.
    PIR-715 builds each arm into the inner tapestry `SubTapestry.__call__`
    already opens and returns its real sink.

    Counts here are the shape of the arm, not a magic number: SIMPLE is
    generate + response; MODERATE adds retrieve + prompt; COMPLEX is three
    retrievers + merge + prompt + generate + response.
    """

    async def _inner_knot_count(self, script: list[str], **kwargs: object) -> tuple[int, int]:
        memory = StubMemoryStore([{"text": "ctx"}])
        llm = StubLLMProvider(script)
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="q",
                memory=memory,
                llm=llm,
                _config=KnotConfig(id="adaptive"),
                **kwargs,  # type: ignore[arg-type]
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        return run.lineage[0].extra["inner_knot_count"], len(memory.search_queries)

    async def test_simple_arm_is_recorded(self) -> None:
        count, searches = await self._inner_knot_count(["SIMPLE", "direct answer"])
        assert count == 2
        assert searches == 0

    async def test_moderate_arm_is_recorded(self) -> None:
        count, searches = await self._inner_knot_count(["MODERATE", "rag answer"], top_k=1)
        assert count == 4
        assert searches == 1

    async def test_complex_arm_is_recorded(self) -> None:
        count, searches = await self._inner_knot_count(
            ["COMPLEX", "s1\ns2\ns3", "mh answer"], top_k=1
        )
        assert count == 7
        assert searches == 3
