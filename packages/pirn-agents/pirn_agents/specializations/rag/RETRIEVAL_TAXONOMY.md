# Agentic RAG — Retrieval Pattern Taxonomy (PAE-F9)

A provider-neutral map of the agentic-RAG patterns shipped by `pirn_agents`,
organised along four axes. Every pattern is a knot (or a small set of knots)
that composes the existing retrieval / embedding / rerank building blocks from
**F4** (`pirn_agents.vector_stores`, `pirn_agents.embeddings`,
`pirn_agents.retrieval`, `pirn_agents.rerank`) and the provider interfaces from
**F3** (`LLMProvider`, `EmbeddingProvider`). No vendor SDK is imported at module
load; every pattern runs on `InMemoryVectorStore` in CI with stub doubles.

The seven pre-existing pipelines (Naive, Corrective, HyDE, Graph, MultiHop,
Self-RAG, Adaptive) already cover the baseline shapes. F9 completes the standard
taxonomy with the patterns below.

---

## The four axes

A RAG pattern intervenes at one (or more) of four points in the
retrieve → synthesize → generate loop:

| Axis | Question it answers | F9 patterns |
|------|--------------------|-------------|
| **Query transformation** | What do we actually search for? | RAG-Fusion (multi-query), Sub-question decomposition, Self-query (metadata extraction), FLARE (forward-looking) |
| **Retrieval strategy** | Where / how do we search, and how many times? | Router RAG, RAG-Fusion (RRF merge), Hybrid (F4), Iterative / Recursive retrieval, Agentic RAG (retrieval-as-tool), Speculative RAG |
| **Post-retrieval** | How do we clean up what we got? | Contextual retrieval + reranking, Contextual compression |
| **Indexing structure** | How is the corpus organised at ingest? | Parent-doc / small-to-big, Sentence-window, Auto-merging, RAPTOR |

---

## Query transformation

### RAG-Fusion (multi-query + RRF) — S2
Reformulate the query into N variants, retrieve each concurrently, fuse the
ranked lists with Reciprocal Rank Fusion.

* Knots: `MultiQueryExpander` (LLM → query variants), `FusionRetriever`
  (concurrent per-variant search + RRF merge), `RagFusionPipeline`.
* Reuses F4: `pirn_agents.retrieval.reciprocal_rank_fusion`.
* F4 dependency: none beyond a `MemoryStore`; hybrid retrieval optional.
* Reference: Rackauckas, "RAG-Fusion" (2024) — https://arxiv.org/abs/2402.03367 ; Cormack et al., RRF (SIGIR 2009).

### Sub-question decomposition — S3
Break a compound query into independent sub-questions, retrieve per
sub-question concurrently, synthesize one grounded answer.

* Knots: `SubQuestionDecomposer`, `SubQuestionRetriever`, `SubQuestionRagPipeline`.
* F4 dependency: `MemoryStore`.
* Reference: Khattab et al., "Demonstrate-Search-Predict" (2022) — https://arxiv.org/abs/2212.14024 .

### Self-query / metadata-filter RAG — S4
Extract a structured metadata filter from natural language, then apply it as a
pre-filter on the vector search.

* Knots: `SelfQueryFilterExtractor` (LLM → `{query, metadata_filter}`),
  `SelfQueryRetriever`, `SelfQueryRagPipeline`.
* **F4 dependency: metadata-filter support** — `VectorMemoryStore.query(..., metadata_filter=...)` and `pirn_agents.vector_stores.metadata_match`.
* Reference: LangChain SelfQueryRetriever design notes.

### FLARE — active retrieval — S9
Generate forward-looking; whenever the next sentence's confidence drops below a
threshold, pause and retrieve before continuing.

* Knots: `SentenceConfidenceMonitor`, `FlareActiveRagPipeline`.
* F4 dependency: `MemoryStore`; bounded by a max-retrieval-calls budget.
* Reference: Jiang et al., "Active Retrieval Augmented Generation" (FLARE, EMNLP 2023) — https://arxiv.org/abs/2305.06983 .

---

## Retrieval strategy

### Router RAG — S4
Classify the query and dispatch it to the best index / strategy.

* Knots: `QueryRouteClassifier` (LLM → route name), `RoutedRetriever`,
  `RouteTable` (opaque name→`MemoryStore` map), `RouterRagPipeline`.
* F4 dependency: one `MemoryStore` per route.
* Reference: LlamaIndex RouterRetriever; Adaptive-RAG (Jeong et al., 2024).

### Iterative / Recursive retrieval + Agentic RAG — S5
Expose RAG as an agent-callable tool (**F6** `RagTool`) so the agent decides
*when* and *what* to retrieve, and loop retrieval under a max-iteration budget
until the evidence is sufficient.

* Knots: `IterativeRetriever` (bounded refine loop), `AgenticRagPipeline`
  (validates a `Tool` via `isinstance`, drives the tool loop).
* Reuses F6: `pirn_agents.tools.retrieval.rag_tool.RagTool`.
* F4 dependency: `MemoryStore`.
* Reference: Asai et al., Self-RAG (2023); Yao et al., ReAct (2022).

### Speculative RAG (draft-then-verify) — S6
Draft a candidate answer from the query alone (fast), retrieve in parallel, then
verify / revise the draft against the retrieved evidence.

* Knots: `SpeculativeDraftGenerator`, `DraftVerifier`, `SpeculativeRagPipeline`.
* Concurrency: draft and retrieval branches run concurrently in the tapestry.
* F4 dependency: `MemoryStore`.
* Reference: Wang et al., "Speculative RAG" (2024) — https://arxiv.org/abs/2407.08223 .

---

## Post-retrieval

### Contextual retrieval + reranking + compression — S7
Situate each chunk in document context, rerank candidates under a top-k budget,
then compress away irrelevant spans while preserving citations.

* Knots: `ContextualChunkEnricher`, `ContextualCompressor`,
  `ContextualRetrievalPipeline`; reranking reuses the existing
  `pirn_agents.specializations.rag.reranker.Reranker`.
* **F4 dependency: rerank support** — `pirn_agents.rerank.reranker_backend.RerankerBackend` (e.g. the cross-encoder adapter), applied under a top-k budget.
* Reference: Anthropic, "Contextual Retrieval" (2024); Nogueira & Cho, BERT re-ranking (2019).

---

## Indexing structure (extends `document_processing/`)

All four reuse the existing sliding-window chunker
(`document_processing._document_chunker._DocumentChunker`) for the primary split
and add only indexing-specific structures under
`specializations/rag/indexing/`. They do **not** introduce a general
chunking-strategy library.

### Parent-doc / small-to-big — S8
Index small child chunks for precision; return their larger parent for context.

* Knots: `ParentDocumentIngestor`, `ParentDocumentRetriever`.

### Sentence-window — S8
Index single sentences; return each hit surrounded by a neighbour window.

* Knots: `SentenceWindowIngestor`, `SentenceWindowRetriever`.

### Auto-merging — S8
Index leaf chunks; when enough leaves of one parent are retrieved, merge up to
the parent.

* Knots: `AutoMergingIngestor`, `AutoMergingRetriever`.

### RAPTOR — S8
Recursively cluster + LLM-summarize chunks into a hierarchical tree, built once
at ingest (content-addressed, reused across queries), queried via collapsed-tree
retrieval.

* Knots: `RaptorTreeBuilder`, `RaptorRetriever`; structures `RaptorNode`,
  `RaptorTree`.
* Content-addressing: the tree root is keyed by a SHA-256 of the corpus; a
  re-ingest of identical content is skipped (no repeated LLM summaries).
* Reference: Sarthi et al., "RAPTOR" (ICLR 2024) — https://arxiv.org/abs/2401.18059 .

---

## F4 dependency summary

| Pattern | Hybrid (dense+lexical) | Rerank | Metadata filter |
|---------|:---:|:---:|:---:|
| RAG-Fusion | optional | — | — |
| Sub-question | optional | — | — |
| Router RAG | optional | — | — |
| Self-query | — | — | **required** |
| Iterative / Agentic | optional | — | — |
| Speculative | — | — | — |
| Contextual + rerank | optional | **required** | — |
| Indexing (S8) | dense | — | uses metadata for parent links |
| FLARE | — | — | — |
