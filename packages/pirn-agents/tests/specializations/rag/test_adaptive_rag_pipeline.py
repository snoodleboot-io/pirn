"""Tests for :class:`AdaptiveRAGPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.adaptive_rag_pipeline import (
    AdaptiveRAGPipeline,
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
        assert response.data == "direct answer"
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
        assert response.data == "rag answer"
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
        assert response.data == "multi-hop answer"
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
        assert response.data == "multi-hop answer"
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
        assert response.data == "direct answer"
        assert memory.search_queries == []


class TestSelectComplexityRoute(unittest.TestCase):
    """Direct coverage of the selector, which sees an upper-cased reply."""

    def test_exact_labels(self) -> None:
        assert AdaptiveRAGPipeline._select_complexity_route("SIMPLE") == "simple"
        assert AdaptiveRAGPipeline._select_complexity_route("MODERATE") == "moderate"
        assert AdaptiveRAGPipeline._select_complexity_route("COMPLEX") == "complex"

    def test_exact_match_wins_over_substring_ordering(self) -> None:
        assert AdaptiveRAGPipeline._select_complexity_route("SIMPLE") == "simple"

    def test_padded_single_label(self) -> None:
        assert AdaptiveRAGPipeline._select_complexity_route("THE ANSWER IS COMPLEX.") == "complex"
        assert AdaptiveRAGPipeline._select_complexity_route("THIS ONE IS SIMPLE.") == "simple"

    def test_hedged_reply_naming_both_labels_resolves_to_complex(self) -> None:
        """A reply naming both labels is irreducibly ambiguous — COMPLEX wins.

        Substring matching cannot tell ``"COMPLEX (not simple)"`` from
        ``"SIMPLE, not complex"``; nor can whole-word matching. Some tiebreak
        has to be picked, and COMPLEX is picked deliberately: routing a simple
        query through multi-hop costs latency and tokens, whereas routing a
        complex query to the direct arm returns a wrong answer. This is the
        recorded decision, not an accident of ordering — see PIR-770.
        """
        assert AdaptiveRAGPipeline._select_complexity_route("COMPLEX (NOT SIMPLE)") == "complex"
        assert AdaptiveRAGPipeline._select_complexity_route("SIMPLE, NOT COMPLEX") == "complex"

    def test_unrecognised_reply_falls_back_to_moderate(self) -> None:
        assert AdaptiveRAGPipeline._select_complexity_route("") == "moderate"
        assert AdaptiveRAGPipeline._select_complexity_route("BANANA") == "moderate"


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def test_process_rejects_non_string_query(self) -> None:
        # PIR-715 added a hand-written guard here because the docstring promised
        # TypeError and nothing delivered it — reached through `__new__`, the
        # call raised AttributeError instead. PIR-734 removed that guard: the
        # promise is now kept by the framework, against the `query: str`
        # annotation, at the point a real caller constructs the knot.
        with self.assertRaises(TypeError):
            AdaptiveRAGPipeline(
                query=123,  # type: ignore[arg-type]
                memory=StubMemoryStore([]),
                llm=StubLLMProvider(["SIMPLE", "answer"]),
                top_k=5,
                _config=KnotConfig(id="x"),
            )


class TestAdaptiveRAGPipelineArmLaziness(unittest.IsolatedAsyncioTestCase):
    """The unselected arms' LLM calls never fire (ADR agents-speaks-core WS5b).

    ``Branch`` unconditionally wires all three arms into the graph (see
    ``TestAdaptiveRAGPipelineArmObservability``), so laziness now comes from
    gating, not from omission. ``StubLLMProvider`` is exhaustive by default
    (a call past the scripted responses raises), so scripting *exactly* the
    number of calls the selected arm needs and asserting ``llm.calls`` has
    that same length, directly, proves the other two arms' generation calls
    were never attempted — not just that the run happened to succeed.
    """

    async def test_simple_route_never_calls_moderate_or_complex_generation(self) -> None:
        memory = StubMemoryStore([{"text": "ctx"}])
        llm = StubLLMProvider(["SIMPLE", "direct answer"])
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="q", memory=memory, llm=llm, _config=KnotConfig(id="adaptive")
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        # classify + generate_simple only -- generate_moderate/decompose/
        # generate (complex) never called.
        assert len(llm.calls) == 2
        assert memory.search_queries == []

    async def test_moderate_route_never_calls_simple_or_complex_generation(self) -> None:
        memory = StubMemoryStore([{"text": "ctx"}])
        llm = StubLLMProvider(["MODERATE", "rag answer"])
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="q", memory=memory, llm=llm, top_k=1, _config=KnotConfig(id="adaptive")
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        # classify + generate_moderate only -- generate_simple/decompose/
        # generate (complex) never called.
        assert len(llm.calls) == 2
        assert len(memory.search_queries) == 1

    async def test_complex_route_never_calls_simple_or_moderate_generation(self) -> None:
        memory = StubMemoryStore([{"text": "ctx"}])
        llm = StubLLMProvider(["COMPLEX", "s1\ns2\ns3", "mh answer"])
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="q", memory=memory, llm=llm, top_k=1, _config=KnotConfig(id="adaptive")
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        # classify + decompose + generate (complex) only -- generate_simple/
        # generate_moderate never called.
        assert len(llm.calls) == 3
        assert len(memory.search_queries) == 3


class TestAdaptiveRAGPipelineArmObservability(unittest.IsolatedAsyncioTestCase):
    """Every arm's knots must belong to the run this pipeline reports.

    Each arm used to open its own `with Tapestry()`, run it via `_run_inner`,
    pull the answer out, and return a `_ResultSource` closure wrapping the
    precomputed value. The pipeline's own inner run therefore contained exactly
    one knot — that closure — on every path, whatever work the arm had done.

    PIR-715 first fixed this by building only the *selected* arm into the
    inner tapestry `SubTapestry.__call__` already opens. ADR agents-speaks-core
    WS5b replaced the Python `if route == ...` with a core `Branch`
    (`route` knot), so now *every* arm is unconditionally wired into the same
    graph — the inner knot count is the fixed shape of all three arms plus the
    branch/classify/fuse scaffolding, not a per-arm number — while gating each
    arm's own entry input on its matching `BranchOutput` keeps only the
    selected arm's LLM/retrieval calls from actually firing. That is what
    `searches` (and, implicitly, `StubLLMProvider` not running out of scripted
    replies) verifies below, not the knot count.
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

    #: classify + route (Branch) + 3 BranchOutputs + generate_simple +
    #: response_simple + retrieve + prompt_moderate + generate_moderate +
    #: response_moderate + response_complex (a nested SubTapestry, one knot
    #: from this run's perspective) + rag_result (Aggregator) == 13, on every
    #: route: all three arms are always wired into the same graph.
    _total_arm_knots = 13

    async def test_simple_arm_is_recorded(self) -> None:
        count, searches = await self._inner_knot_count(["SIMPLE", "direct answer"])
        assert count == self._total_arm_knots
        assert searches == 0

    async def test_moderate_arm_is_recorded(self) -> None:
        count, searches = await self._inner_knot_count(["MODERATE", "rag answer"], top_k=1)
        assert count == self._total_arm_knots
        assert searches == 1

    async def test_complex_arm_is_recorded(self) -> None:
        count, searches = await self._inner_knot_count(
            ["COMPLEX", "s1\ns2\ns3", "mh answer"], top_k=1
        )
        assert count == self._total_arm_knots
        assert searches == 3
