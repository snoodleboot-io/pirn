`pirn_agents.specializations.rag` provides retrieval-augmented generation pipelines built on top of the agent tier knots — it does not implement vector storage or embedding; those are user-supplied via a `MemoryStore` and an embedding knot.

---

## Mental model

Every RAG pipeline follows the same three-stage shape: **retrieve** (search the memory store), **synthesize** (build a prompt from retrieved chunks + question), **generate** (call the LLM). Pre-built pipeline knots (`NaiveRAGPipeline`, `CorrectiveRAGPipeline`, etc.) compose the stages. Use individual stage knots (`MemorySearchRetriever`, `RAGPromptBuilder`, `RAGSynthesizer`) when you need to customize a specific stage.

Pipelines differ in how they handle retrieval quality: Naive trusts the retriever; Corrective re-routes on low-relevance; Self-RAG decides when retrieval is needed; Multi-Hop chains retrievals; HyDE generates a hypothetical answer before retrieving; Graph RAG traverses a knowledge graph; Adaptive picks the best strategy dynamically.

---

## Source map

```
pirn_agents/specializations/rag/
│
│  ── Stage knots ──
├── memory_search_retriever.py    MemorySearchRetriever    — query memory store; return top-K chunks
├── rag_prompt_builder.py         RAGPromptBuilder         — assemble system+context+question prompt
├── rag_synthesizer.py            RAGSynthesizer           — call LLM with assembled prompt; return answer
├── rag_response_builder.py       RAGResponseBuilder       — format answer with citations
├── reranker.py                   Reranker                 — re-rank retrieved chunks by relevance score
├── relevance_check.py            RelevanceCheck           — pass chunks above threshold; Skipped below
│
│  ── Corrective RAG helpers ──
├── corrective_router.py          CorrectiveRouter         — route to web search if retrieval score is low
│
│  ── Graph RAG helpers ──
├── sub_graph_context_builder.py  SubGraphContextBuilder   — extract sub-graph neighbourhood as context
│
│  ── Pipeline knots ──
├── naive_rag_pipeline.py         NaiveRAGPipeline         — retrieve → synthesize; no quality check
├── corrective_rag_pipeline.py    CorrectiveRAGPipeline    — retrieve → relevance gate → (re-retrieve or web) → synthesize
├── self_rag_pipeline.py          SelfRAGPipeline          — decide if retrieval needed; retrieve → critique → answer
├── multi_hop_rag_pipeline.py     MultiHopRAGPipeline      — chain N retrievals, each refining the query
├── hyde_rag_pipeline.py          HyDERAGPipeline          — generate hypothetical doc → embed → retrieve → answer
├── graph_rag_pipeline.py         GraphRAGPipeline         — entity extraction → graph traversal → synthesize
├── adaptive_rag_pipeline.py      AdaptiveRAGPipeline      — classify query complexity; dispatch to appropriate RAG variant
│
│  ── Shared ──
└── llm_chat_call.py              LLMChatCall              — thin wrapper: messages → LLM response string
```

---

## Canonical pattern

### Naive RAG

```python
from pirn_agents.specializations.rag.naive_rag_pipeline import NaiveRAGPipeline
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

with Tapestry() as t:
    question = Parameter("question", str)
    answer   = NaiveRAGPipeline(
        question=question,
        memory_store=my_vector_store,
        llm=my_llm_caller,
        top_k=5,
        _config=KnotConfig(id="rag"),
    )

result = await t.run(RunRequest(parameters={"question": "What is the capital of France?"}))
```

### Corrective RAG — fall back to web search on low relevance

```python
from pirn_agents.specializations.rag.corrective_rag_pipeline import CorrectiveRAGPipeline

with Tapestry() as t:
    question = Parameter("question", str)
    answer   = CorrectiveRAGPipeline(
        question=question,
        memory_store=my_vector_store,
        fallback_search=my_web_search_tool,
        llm=my_llm_caller,
        relevance_threshold=0.7,
        _config=KnotConfig(id="corrective-rag"),
    )
```

### Custom pipeline using stage knots

```python
from pirn_agents.specializations.rag.memory_search_retriever import MemorySearchRetriever
from pirn_agents.specializations.rag.reranker import Reranker
from pirn_agents.specializations.rag.rag_synthesizer import RAGSynthesizer

with Tapestry() as t:
    question = Parameter("question", str)
    chunks   = MemorySearchRetriever(query=question, memory_store=store, top_k=20,
                                     _config=KnotConfig(id="retrieve"))
    reranked = Reranker(chunks=chunks, query=question, top_k=5,
                        _config=KnotConfig(id="rerank"))
    answer   = RAGSynthesizer(chunks=reranked, question=question, llm=llm,
                               _config=KnotConfig(id="synthesize"))
```

---

## Anti-patterns

**Using `NaiveRAGPipeline` for knowledge-intensive questions** — if the retriever can miss or return low-quality chunks, use `CorrectiveRAGPipeline` or `AdaptiveRAGPipeline` to handle retrieval failures.

**Setting `top_k` too high without a reranker** — large `top_k` bloats the context window. Use `Reranker` to keep only the most relevant chunks after a wide retrieval.

**Using `HyDERAGPipeline` for factual lookups** — HyDE works best for abstract or conceptual queries. For precise factual lookups, naive or corrective RAG is faster and more reliable.

---

## Constraints and gotchas

- **`MemorySearchRetriever` requires a `MemoryStore`** — any object implementing the `MemoryStore` interface from `pirn_agents.knots`.
- **`GraphRAGPipeline` requires a graph store** (Neo4j, Memgraph, or ArangoDB pool) in addition to a vector store for entity resolution.
- **`AdaptiveRAGPipeline` uses an LLM call to classify the query.** This adds one extra LLM call per invocation — budget accordingly.
- **`MultiHopRAGPipeline(max_hops=N)` defaults to `max_hops=3`.** Each hop is a retrieval + LLM call chain; latency scales linearly.

---

## Quick reference

| Task | Pipeline |
|------|---------|
| Simple RAG (trust retriever) | `NaiveRAGPipeline` |
| RAG with fallback on low relevance | `CorrectiveRAGPipeline` |
| RAG that decides when to retrieve | `SelfRAGPipeline` |
| Multi-step reasoning over docs | `MultiHopRAGPipeline` |
| Abstract/conceptual queries | `HyDERAGPipeline` |
| Entities + relationships in docs | `GraphRAGPipeline` |
| Mixed query types | `AdaptiveRAGPipeline` |
| Custom stage assembly | `MemorySearchRetriever` + `Reranker` + `RAGSynthesizer` |

---

*See also: [specializations AGENTIC_USE.md](../AGENTIC_USE.md)*
