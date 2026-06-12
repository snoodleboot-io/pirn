`pirn.domains.agents.specializations.document_processing` provides pipelines for ingesting, querying, summarizing, and translating documents — it does not implement chunking strategies or embedding models; those are user-supplied via a `FileFormat`, a chunker callable, and an embedding knot.

---

## Mental model

Document processing has two phases: **ingestion** (load → chunk → embed → store) and **retrieval** (load → chunk → retrieve → answer/summarize/translate). The pipelines here handle both phases as composable pipeline knots. Internal helper knots (prefixed `_`) are wired by the pipeline constructors — you rarely need to use them directly.

---

## Source map

```
pirn/domains/agents/specializations/document_processing/
│
│  ── Ingestion ──
├── document_ingestion_pipeline.py     DocumentIngestionPipeline    — load + chunk + embed + store
├── embedding_indexer.py               EmbeddingIndexer             — embed chunks; write to memory store
├── metadata_extractor.py              MetadataExtractor            — extract title, author, date, etc. from a document
│
│  ── Question answering ──
├── document_qa_pipeline.py            DocumentQaPipeline           — load + chunk + retrieve + answer
│
│  ── Summarization ──
├── document_summarizer_pipeline.py    DocumentSummarizerPipeline   — map-reduce summarization over chunks
│
│  ── Translation ──
├── document_translation_pipeline.py   DocumentTranslationPipeline  — chunk + translate per-chunk + reassemble
│
│  ── Internal helpers ──
├── _document_loader.py                (load bytes from path/store)
├── _document_chunker.py               (split document into chunks)
├── _chunk_embedder_store.py           (embed + persist chunks)
├── _chunk_translator.py               (translate a single chunk)
├── _load_and_chunk.py                 (loader + chunker combined)
├── _map_reduce_summariser.py          (map: summarize chunk; reduce: combine)
├── _qa_load_and_chunk.py              (QA: load, chunk, retrieve)
├── _qa_retrieve_and_answer.py         (QA: retrieve chunks, call LLM)
└── _translation_load_and_chunk.py     (translation: load, chunk)
```

---

## Canonical pattern

### Ingest a document into a vector store

```python
from pirn.domains.agents.specializations.document_processing.document_ingestion_pipeline import DocumentIngestionPipeline
from pirn.connectors.file_formats.pdf_format import PdfFormat
from pirn import Tapestry, Parameter, KnotConfig, RunRequest

with Tapestry() as t:
    doc_bytes = Parameter("doc_bytes", bytes)
    DocumentIngestionPipeline(
        document=doc_bytes,
        file_format=PdfFormat(),
        chunker=my_sentence_chunker,
        embedder=my_embedding_knot,
        store=my_vector_store,
        _config=KnotConfig(id="ingest"),
    )

result = await t.run(RunRequest(parameters={"doc_bytes": pdf_bytes}))
```

### Question answering over a document

```python
from pirn.domains.agents.specializations.document_processing.document_qa_pipeline import DocumentQaPipeline

with Tapestry() as t:
    question  = Parameter("question", str)
    doc_bytes = Parameter("doc_bytes", bytes)
    answer    = DocumentQaPipeline(
        question=question,
        document=doc_bytes,
        file_format=PdfFormat(),
        chunker=my_chunker,
        embedder=my_embedder,
        store=my_vector_store,
        llm=my_llm,
        _config=KnotConfig(id="qa"),
    )
```

### Summarize a long document

```python
from pirn.domains.agents.specializations.document_processing.document_summarizer_pipeline import DocumentSummarizerPipeline

with Tapestry() as t:
    doc_bytes = Parameter("doc_bytes", bytes)
    summary   = DocumentSummarizerPipeline(
        document=doc_bytes,
        file_format=PdfFormat(),
        chunker=my_chunker,
        llm=my_llm,
        _config=KnotConfig(id="summarize"),
    )
```

---

## Anti-patterns

**Calling `DocumentIngestionPipeline` and `DocumentQaPipeline` in the same tapestry run** — ingest first (writes to store), then query in a separate run. Running both in the same tapestry means the QA pipeline reads from the store before ingestion has committed.

**Setting chunk size without considering the LLM's context window** — each chunk is sent to the LLM during summarization or QA. Chunk size × top_k must fit the context window with room for the system prompt and response.

---

## Constraints and gotchas

- **`DocumentSummarizerPipeline` uses map-reduce** — it summarizes each chunk independently, then summarizes the summaries. For short documents, the overhead may exceed the benefit. Use a direct LLM call for documents under ~2,000 tokens.
- **`DocumentTranslationPipeline` translates chunk-by-chunk.** Sentence boundaries at chunk edges may lose context. Use larger `chunk_size` for translation than for retrieval.
- **`MetadataExtractor` uses an LLM call.** It adds one LLM call per document during ingestion. Disable it by not including it if metadata is not needed.

---

## Quick reference

| Task | Pipeline |
|------|---------|
| Load + chunk + embed + store | `DocumentIngestionPipeline` |
| Ask a question about a document | `DocumentQaPipeline` |
| Summarize a long document | `DocumentSummarizerPipeline` |
| Translate a document | `DocumentTranslationPipeline` |
| Extract document metadata | `MetadataExtractor` |
| Embed + index pre-chunked content | `EmbeddingIndexer` |

---

*See also: [specializations AGENTIC_USE.md](../AGENTIC_USE.md)*
