`pirn_agents.specializations.rag` provides retrieval-augmented generation pipelines built on top of the agent tier knots — it does not implement vector storage or embedding; those are user-supplied via a `MemoryStore` and an embedding knot.

---

## Mental model

Every RAG pipeline follows the same three-stage shape: **retrieve** (search the memory store), **synthesize** (build a prompt from retrieved chunks + question), **generate** (call the LLM). Pre-built pipeline knots (`NaiveRagPipeline`, `CorrectiveRagPipeline`, etc.) compose the stages. Use individual stage knots (`MemorySearchRetriever`, `RagPromptBuilder`, `RagSynthesizer`) when you need to customize a specific stage.

Pipelines differ in how they handle retrieval quality: Naive trusts the retriever; Corrective re-routes on low-relevance; Self-RAG decides when retrieval is needed; Multi-Hop chains retrievals; HyDE generates a hypothetical answer before retrieving; Graph RAG traverses a knowledge graph; Adaptive picks the best strategy dynamically.

---

## Source map

```
pirn_agents/specializations/rag/
│
│  ── Stage knots ──
├── memory_search_retriever.py    MemorySearchRetriever    — query memory store; return top-K chunks
├── rag_prompt_builder.py         RagPromptBuilder         — assemble system+context+question prompt
├── rag_synthesizer.py            RagSynthesizer           — call LLM with assembled prompt; return answer
├── rag_response_builder.py       RagResponseBuilder       — format answer with citations
├── reranker.py                   Reranker                 — re-rank retrieved chunks by relevance score
├── relevance_gate.py             RelevanceGate            — pass chunks above threshold; Skipped below
│
│  ── Corrective RAG helpers ──
├── corrective_router.py          CorrectiveRouter         — route to web search if retrieval score is low
│
│  ── Graph RAG helpers ──
├── sub_graph_context_builder.py  SubGraphContextBuilder   — extract sub-graph neighbourhood as context
│
│  ── Pipeline knots ──
├── naive_rag_pipeline.py         NaiveRagPipeline         — retrieve → synthesize; no quality check
├── corrective_rag_pipeline.py    CorrectiveRagPipeline    — retrieve → relevance gate → (re-retrieve or web) → synthesize
├── self_rag_pipeline.py          SelfRagPipeline          — decide if retrieval needed; retrieve → critique → answer
├── multi_hop_rag_pipeline.py     MultiHopRagPipeline      — chain N retrievals, each refining the query
├── hyde_rag_pipeline.py          HydeRagPipeline          — generate hypothetical doc → embed → retrieve → answer
├── graph_rag_pipeline.py         GraphRagPipeline         — entity extraction → graph traversal → synthesize
├── adaptive_rag_pipeline.py      AdaptiveRagPipeline      — classify query complexity; dispatch to appropriate RAG variant
│
│  ── Shared ──
└── llm_chat_call.py              LlmChatCall              — thin wrapper: messages → LLM response string
```

---

## Canonical pattern

### Naive RAG

```python
from pirn_agents.specializations.rag.naive_rag_pipeline import NaiveRagPipeline
from pirn import Tapestry, Parameter, KnotConfig, RunRequest

with Tapestry() as t:
    question = Parameter("question", str)
    answer   = NaiveRagPipeline(
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
from pirn_agents.specializations.rag.corrective_rag_pipeline import CorrectiveRagPipeline

with Tapestry() as t:
    question = Parameter("question", str)
    answer   = CorrectiveRagPipeline(
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
from pirn_agents.specializations.rag.rag_synthesizer import RagSynthesizer

with Tapestry() as t:
    question = Parameter("question", str)
    chunks   = MemorySearchRetriever(query=question, memory_store=store, top_k=20,
                                     _config=KnotConfig(id="retrieve"))
    reranked = Reranker(chunks=chunks, query=question, top_k=5,
                        _config=KnotConfig(id="rerank"))
    answer   = RagSynthesizer(chunks=reranked, question=question, llm=llm,
                               _config=KnotConfig(id="synthesize"))
```

---

## Anti-patterns

**Using `NaiveRagPipeline` for knowledge-intensive questions** — if the retriever can miss or return low-quality chunks, use `CorrectiveRagPipeline` or `AdaptiveRagPipeline` to handle retrieval failures.

**Setting `top_k` too high without a reranker** — large `top_k` bloats the context window. Use `Reranker` to keep only the most relevant chunks after a wide retrieval.

**Using `HydeRagPipeline` for factual lookups** — HyDE works best for abstract or conceptual queries. For precise factual lookups, naive or corrective RAG is faster and more reliable.

---

## Constraints and gotchas

- **`MemorySearchRetriever` requires a `MemoryStore`** — any object implementing the `MemoryStore` interface from `pirn_agents.knots`.
- **`GraphRagPipeline` requires a graph store** (Neo4j, Memgraph, or ArangoDB pool) in addition to a vector store for entity resolution.
- **`AdaptiveRagPipeline` uses an LLM call to classify the query.** This adds one extra LLM call per invocation — budget accordingly.
- **`MultiHopRagPipeline(max_hops=N)` defaults to `max_hops=3`.** Each hop is a retrieval + LLM call chain; latency scales linearly.

---

## Quick reference

| Task | Pipeline |
|------|---------|
| Simple RAG (trust retriever) | `NaiveRagPipeline` |
| RAG with fallback on low relevance | `CorrectiveRagPipeline` |
| RAG that decides when to retrieve | `SelfRagPipeline` |
| Multi-step reasoning over docs | `MultiHopRagPipeline` |
| Abstract/conceptual queries | `HydeRagPipeline` |
| Entities + relationships in docs | `GraphRagPipeline` |
| Mixed query types | `AdaptiveRagPipeline` |
| Custom stage assembly | `MemorySearchRetriever` + `Reranker` + `RagSynthesizer` |

---

*See also: [specializations AGENTIC_USE.md](../AGENTIC_USE.md)*
