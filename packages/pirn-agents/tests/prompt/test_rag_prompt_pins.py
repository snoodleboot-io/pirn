"""Byte-identity pins for every prompt shipped inside ``specializations/rag``.

Each test drives the owning knot (or its prompt helper) with stub providers and
asserts the exact text that reaches ``LLMProvider.chat``. The expected strings
are copied byte-for-byte from the pre-WS6 inline literals, so these pins fail the
moment routing a prompt through :class:`PromptBinding` alters delivered text.

Written before the WS6-S1 stage-B conversion and green on the unconverted
source; the conversion must keep them green without edits.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_agents.specializations.rag.adaptive_rag_pipeline import AdaptiveRAGPipeline
from pirn_agents.specializations.rag.agentic_rag_pipeline import AgenticRagPipeline
from pirn_agents.specializations.rag.contextual_chunk_enricher import ContextualChunkEnricher
from pirn_agents.specializations.rag.contextual_compressor import ContextualCompressor
from pirn_agents.specializations.rag.draft_verifier import DraftVerifier
from pirn_agents.specializations.rag.flare_active_rag_pipeline import FlareActiveRagPipeline
from pirn_agents.specializations.rag.graph_rag_pipeline import GraphRAGPipeline
from pirn_agents.specializations.rag.hyde_rag_pipeline import HyDERAGPipeline
from pirn_agents.specializations.rag.indexing._raptor_assembler import _RaptorAssembler
from pirn_agents.specializations.rag.iterative_retriever import IterativeRetriever
from pirn_agents.specializations.rag.multi_hop_rag_pipeline import MultiHopRAGPipeline
from pirn_agents.specializations.rag.multi_query_expander import MultiQueryExpander
from pirn_agents.specializations.rag.query_route_classifier import QueryRouteClassifier
from pirn_agents.specializations.rag.rag_prompt_builder import RAGPromptBuilder
from pirn_agents.specializations.rag.rag_synthesizer import RAGSynthesizer
from pirn_agents.specializations.rag.reranker import Reranker
from pirn_agents.specializations.rag.self_query_filter_extractor import SelfQueryFilterExtractor
from pirn_agents.specializations.rag.self_rag_pipeline import SelfRAGPipeline
from pirn_agents.specializations.rag.speculative_draft_generator import SpeculativeDraftGenerator
from pirn_agents.specializations.rag.sub_question_decomposer import SubQuestionDecomposer

from tests.specializations.conftest import StubLLMProvider, StubMemoryStore


class RagPipelinePromptPins(unittest.IsolatedAsyncioTestCase):
    """Prompts assembled inside a nested ``Tapestry`` reach the LLM unchanged."""

    async def test_adaptive_classify_prompt(self) -> None:
        llm = StubLLMProvider(["SIMPLE", "answer"])
        with Tapestry() as tapestry:
            AdaptiveRAGPipeline(
                query="Q",
                memory=StubMemoryStore([]),
                llm=llm,
                _config=KnotConfig(id="adaptive"),
            )
        await tapestry.run(RunRequest())
        assert llm.calls[0][0]["content"] == (
            "Classify the complexity of the following question as one of: "
            "SIMPLE, MODERATE, or COMPLEX. "
            "SIMPLE means it can be answered directly without external context. "
            "MODERATE means a single retrieval step suffices. "
            "COMPLEX means it requires multiple reasoning steps or sub-questions. "
            "Reply with only the single word.\n\n"
            "Question: Q"
        )

    async def test_adaptive_decompose_prompt(self) -> None:
        llm = StubLLMProvider(["COMPLEX", "a\nb\nc", "answer"])
        with Tapestry() as tapestry:
            AdaptiveRAGPipeline(
                query="Q",
                memory=StubMemoryStore([{"text": "ctx"}]),
                llm=llm,
                top_k=1,
                _config=KnotConfig(id="adaptive"),
            )
        await tapestry.run(RunRequest())
        assert llm.calls[1][0]["content"] == (
            "Decompose the following question into exactly three concise "
            "sub-questions, one per line, no numbering or bullets.\n\n"
            "Question: Q"
        )

    async def test_graph_rag_instruction(self) -> None:
        llm = StubLLMProvider(["answer"])
        with Tapestry() as tapestry:
            GraphRAGPipeline(
                query="Q",
                graph_memory=StubMemoryStore([]),
                llm=llm,
                hop_count=2,
                _config=KnotConfig(id="grag"),
            )
        await tapestry.run(RunRequest())
        body = str(llm.calls[0][-1]["content"])
        assert body.split("\n\nContext:\n", 1)[0] == (
            "Answer the question using the retrieved sub-graph "
            "context. Cite entities by id when relevant."
        )

    async def test_hyde_hypothesis_prompt(self) -> None:
        llm = StubLLMProvider(["hypothesis", "answer"])
        with Tapestry() as tapestry:
            HyDERAGPipeline(
                query="Q",
                memory=StubMemoryStore([]),
                llm=llm,
                _config=KnotConfig(id="hyde"),
            )
        await tapestry.run(RunRequest())
        assert llm.calls[0][0]["content"] == (
            "Sketch a concise hypothetical answer to the following question. "
            "Use plausible terminology even if uncertain.\n\n"
            "Question: Q\nHypothetical answer:"
        )

    async def test_multi_hop_decompose_prompt(self) -> None:
        llm = StubLLMProvider(["a\nb\nc", "answer"])
        with Tapestry() as tapestry:
            MultiHopRAGPipeline(
                query="Q",
                memory=StubMemoryStore([]),
                llm=llm,
                top_k=1,
                num_hops=3,
                _config=KnotConfig(id="multihop"),
            )
        await tapestry.run(RunRequest())
        assert llm.calls[0][0]["content"] == (
            "Decompose the following question into exactly 3 "
            "concise sub-questions, one per line, with no numbering or bullets.\n\n"
            "Question: Q"
        )

    async def test_self_rag_assess_prompt(self) -> None:
        llm = StubLLMProvider(["DRAFT", "NO"])
        with Tapestry() as tapestry:
            SelfRAGPipeline(
                query="Q",
                memory=StubMemoryStore([]),
                llm=llm,
                _config=KnotConfig(id="selfrag"),
            )
        await tapestry.run(RunRequest())
        assert llm.calls[1][0]["content"] == (
            "Given the following question and draft answer, decide if "
            "retrieval of additional context is needed to give a more "
            "accurate or complete answer. Reply with only YES or NO.\n\n"
            "Question: Q\nDraft answer: DRAFT"
        )

    async def test_rag_prompt_builder_default_instruction(self) -> None:
        with Tapestry() as tapestry:
            RAGPromptBuilder(query="Q", retrieved=[], _config=KnotConfig(id="prompt"))
        result = await tapestry.run(RunRequest())
        assert result.outputs["prompt"] == (
            "Answer the question using the retrieved context."
            "\n\nContext:\n(no context retrieved)\n\nQuestion: Q\nAnswer:"
        )


class RagKnotPromptPins(unittest.IsolatedAsyncioTestCase):
    """Prompts built directly inside ``process()`` reach the LLM unchanged."""

    async def test_contextual_chunk_enricher_prompt(self) -> None:
        llm = StubLLMProvider(["ctx"])
        knot = ContextualChunkEnricher(
            documents=[],
            document_text="D",
            llm=llm,
            _config=KnotConfig(id="enrich"),
        )
        await knot.process(documents=[{"text": "C"}], document_text="D", llm=llm)
        assert llm.calls[0][0]["content"] == (
            "Give a single short sentence that situates the following chunk within the "
            "document, so it can be understood in isolation. Reply with only the sentence.\n\n"
            "Document:\nD\n\nChunk:\nC"
        )

    async def test_contextual_compressor_prompt(self) -> None:
        llm = StubLLMProvider(["kept"])
        knot = ContextualCompressor(
            query="Q",
            documents=[],
            llm=llm,
            _config=KnotConfig(id="compress"),
        )
        await knot.process(query="Q", documents=[{"text": "D"}], llm=llm)
        assert llm.calls[0][0]["content"] == (
            "Extract only the sentences from the document that are relevant to the "
            "query. Preserve wording exactly. If nothing is relevant, reply with only "
            "'NONE'.\n\nQuery: Q\n\nDocument:\nD"
        )

    async def test_draft_verifier_prompt(self) -> None:
        llm = StubLLMProvider(["verified"])
        knot = DraftVerifier(
            query="Q",
            draft="DR",
            documents=[],
            llm=llm,
            _config=KnotConfig(id="verify"),
        )
        await knot.process(query="Q", draft="DR", documents=[{"text": "S"}], llm=llm)
        assert llm.calls[0][0]["content"] == (
            "A draft answer was written before sources were consulted. Verify it against "
            "the sources below: keep what they support, correct what they contradict, and "
            "cite the sources you rely on using their bracketed numbers.\n\n"
            "Question: Q\n\nDraft answer: DR\n\nSources:\n[1] S\n\n"
            "Verified answer:"
        )

    async def test_multi_query_expander_prompt(self) -> None:
        llm = StubLLMProvider(["v1\nv2"])
        knot = MultiQueryExpander(query="Q", llm=llm, _config=KnotConfig(id="expand"))
        await knot.process(query="Q", llm=llm, num_queries=3)
        assert llm.calls[0][0]["content"] == (
            "Rewrite the following search query into 2 alternative "
            "phrasings that would retrieve relevant but differently-worded documents. "
            "Return one phrasing per line with no numbering or commentary.\n\n"
            "Query: Q"
        )

    async def test_query_route_classifier_prompt(self) -> None:
        llm = StubLLMProvider(["a"])
        knot = QueryRouteClassifier(
            query="Q",
            llm=llm,
            route_names=["a", "b"],
            _config=KnotConfig(id="route"),
        )
        await knot.process(query="Q", llm=llm, route_names=["a", "b"])
        assert llm.calls[0][0]["content"] == (
            "Choose the single most appropriate route for the query from this list: "
            "a, b. Reply with only the route name.\n\nQuery: Q"
        )

    async def test_rag_synthesizer_prompt(self) -> None:
        llm = StubLLMProvider(["answer"])
        knot = RAGSynthesizer(
            query="Q",
            documents=[],
            llm=llm,
            _config=KnotConfig(id="synth"),
        )
        await knot.process(query="Q", documents=[{"text": "S"}], llm=llm)
        assert llm.calls[0][0]["content"] == (
            "Answer the following question using only the provided source "
            "passages. Cite each passage you draw on using its bracketed "
            "number (e.g. [1]).\n\n"
            "Question: Q\n\n"
            "Sources:\n[1] S\n\n"
            "Answer:"
        )

    async def test_reranker_score_prompt(self) -> None:
        llm = StubLLMProvider(["0.5"])
        knot = Reranker(
            query="Q",
            documents=[],
            llm=llm,
            _config=KnotConfig(id="rerank"),
        )
        await knot.process(query="Q", documents=[{"text": "D"}], llm=llm, top_k=1)
        assert llm.calls[0][0]["content"] == (
            "Score the relevance of the following document to the query "
            "on a scale from 0.0 (not relevant) to 1.0 (highly relevant). "
            "Reply with only the numeric score.\n\n"
            "Query: Q\n\nDocument: D"
        )

    async def test_self_query_filter_extractor_prompt(self) -> None:
        llm = StubLLMProvider(['{"query": "Q", "filter": {}}'])
        knot = SelfQueryFilterExtractor(
            query="Q",
            llm=llm,
            filterable_fields=["a", "b"],
            _config=KnotConfig(id="selfquery"),
        )
        await knot.process(query="Q", llm=llm, filterable_fields=["a", "b"])
        assert llm.calls[0][0]["content"] == (
            "Split the query into a semantic search string and structured metadata "
            "filters. Only use these filter fields: "
            "a, b. Respond with a JSON object of the form "
            '{"query": "<semantic text>", "filter": {"field": value}}. '
            "Use an empty filter object when no structured constraint applies.\n\n"
            "Query: Q"
        )

    async def test_speculative_draft_generator_prompt(self) -> None:
        llm = StubLLMProvider(["draft"])
        knot = SpeculativeDraftGenerator(query="Q", llm=llm, _config=KnotConfig(id="draft"))
        await knot.process(query="Q", llm=llm)
        assert llm.calls[0][0]["content"] == (
            "Give a concise best-effort answer to the question from your own knowledge. "
            "This is a fast draft that will be verified against sources afterwards.\n\n"
            "Question: Q\nDraft answer:"
        )

    async def test_sub_question_decomposer_prompt(self) -> None:
        llm = StubLLMProvider(["s1\ns2"])
        knot = SubQuestionDecomposer(query="Q", llm=llm, _config=KnotConfig(id="decompose"))
        await knot.process(query="Q", llm=llm, max_sub_questions=2)
        assert llm.calls[0][0]["content"] == (
            "Break the following question into at most 2 independent, "
            "self-contained sub-questions that together cover it. Return one sub-question "
            "per line with no numbering or commentary.\n\n"
            "Question: Q"
        )


class RagHelperPromptPins(unittest.IsolatedAsyncioTestCase):
    """Prompts built by private helpers reach the LLM unchanged."""

    async def test_agentic_next_question_prompt(self) -> None:
        llm = StubLLMProvider(["DONE"])
        await AgenticRagPipeline._next_question(llm, "Q", "A")
        assert llm.calls[0][0]["content"] == (
            "You are an agent answering a question with a retrieval tool. Given the "
            "original question and the tool's latest answer, reply with exactly 'DONE' if "
            "the answer fully resolves the question, or 'FOLLOWUP: <a more specific "
            "question>' otherwise.\n\nOriginal question: Q\n\nLatest answer: A"
        )

    async def test_flare_generate_prompt(self) -> None:
        assert FlareActiveRagPipeline._generate_prompt("Q", []) == (
            "Answer the question one sentence at a time. Reply with 'DONE' if the answer is "
            "complete, otherwise reply exactly 'CONF=<0-1>: <the next sentence>' where the number "
            "is your confidence.\n\nQuestion: Q\n\nAnswer so far: (nothing yet)"
        )

    async def test_flare_regenerate_prompt(self) -> None:
        assert FlareActiveRagPipeline._regenerate_prompt("Q", "S", []) == (
            "Rewrite the tentative sentence so it is fully supported by the evidence. Reply with "
            "only the corrected sentence.\n\nQuestion: Q\n\nTentative sentence: S\n\n"
            "Evidence:\n(no evidence retrieved)"
        )

    async def test_iterative_retriever_decide_prompt(self) -> None:
        llm = StubLLMProvider(["DONE"])
        await IterativeRetriever._decide(llm, "OQ", {}, "CQ")
        assert llm.calls[0][0]["content"] == (
            "You are running iterative retrieval. Given the original question and the "
            "evidence gathered so far, reply with exactly 'DONE' if the evidence is "
            "sufficient, or 'REFINE: <a sharper follow-up search query>' if more is "
            "needed.\n\nOriginal question: OQ\n"
            "Last query: CQ\n\nEvidence:\n(nothing yet)"
        )

    async def test_raptor_summarize_prompt(self) -> None:
        llm = StubLLMProvider(["summary"])
        await _RaptorAssembler._summarize(llm, ["a", "b"])
        assert llm.calls[0][0]["content"] == (
            "Summarize the following passages into one concise summary that preserves the "
            "key facts.\n\na\n\nb\n\nSummary:"
        )
