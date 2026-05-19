`pirn.domains.agents.specializations.memory_patterns` provides pipelines for the four memory types used in agent systems — it does not store data itself; all persistence goes through a `MemoryStore` (vector store) and optionally a structured database pool.

---

## Mental model

The four memory types map to how humans organize knowledge:
- **Working memory** — recent messages in the current session; stored in-context as a sliding window
- **Episodic memory** — records of past events (what happened, when, outcome); retrieved by similarity
- **Semantic memory** — factual knowledge extracted from interactions; deduplicated and upserted
- **Procedural memory** — learned action sequences and preferences; retrieved to guide decisions

Each type has a `*Pipeline` (the complete read-write pattern), a writer, and a retriever. Mix types as needed — most production agents use working + episodic at minimum.

---

## Source map

```
pirn/domains/agents/specializations/memory_patterns/
│
│  ── Working memory ──
├── working_memory_pipeline.py        WorkingMemoryPipeline       — maintain sliding window of recent messages
├── working_memory_window_writer.py   WorkingMemoryWindowWriter   — write new message; evict oldest if over limit
│
│  ── Episodic memory ──
├── episodic_memory_pipeline.py       EpisodicMemoryPipeline      — retrieve past episodes; write new episode after run
├── episodic_episode_writer.py        EpisodicEpisodeWriter       — embed + store a completed interaction as an episode
├── episodic_memory_retriever.py      EpisodicMemoryRetriever     — retrieve K most similar past episodes by query
│
│  ── Semantic memory ──
├── semantic_memory_pipeline.py       SemanticMemoryPipeline      — extract facts from interaction; upsert into store
├── semantic_fact_extractor.py        SemanticFactExtractor       — LLM extracts verifiable facts from text
├── semantic_fact_writer.py           SemanticFactWriter          — embed + write facts to memory store
├── semantic_memory_upsert.py         SemanticMemoryUpsert        — deduplicate facts before writing (update if similar exists)
│
│  ── Procedural memory ──
├── procedural_memory_pipeline.py     ProceduralMemoryPipeline    — retrieve procedures; update on new observations
└── procedural_memory_writer.py       ProceduralMemoryWriter      — write a new procedure or preference to store
│
│  ── Shared ──
└── session_summarizer.py             SessionSummarizer           — summarize a session for long-term storage
```

---

## Canonical pattern

### Working + episodic memory for a conversational agent

```python
from pirn.domains.agents.specializations.memory_patterns.working_memory_pipeline import WorkingMemoryPipeline
from pirn.domains.agents.specializations.memory_patterns.episodic_memory_pipeline import EpisodicMemoryPipeline
from pirn import Tapestry, Parameter, KnotConfig, RunRequest

with Tapestry() as t:
    user_message  = Parameter("user_message", str)
    working_ctx   = WorkingMemoryPipeline(
        message=user_message,
        store=session_store,
        window_size=20,
        _config=KnotConfig(id="working-mem"),
    )
    episode_ctx   = EpisodicMemoryPipeline(
        query=user_message,
        store=episodic_store,
        top_k=3,
        _config=KnotConfig(id="episodic-mem"),
    )
    response      = LlmCaller(
        prompt=ContextAssembler(working=working_ctx, episodic=episode_ctx, ...),
        llm=my_llm,
        _config=KnotConfig(id="llm"),
    )
```

### Extract and persist semantic facts after a session

```python
from pirn.domains.agents.specializations.memory_patterns.semantic_memory_pipeline import SemanticMemoryPipeline

with Tapestry() as t:
    session_text = Parameter("session_text", str)
    SemanticMemoryPipeline(
        text=session_text,
        store=knowledge_store,
        llm=my_llm,
        _config=KnotConfig(id="learn"),
    )
```

---

## Anti-patterns

**Using working memory as long-term storage** — working memory is in-context; it evicts old messages as the window fills. Use episodic or semantic memory for anything that must persist beyond the current session.

**Running `SemanticMemoryPipeline` on every turn** — fact extraction is an LLM call. Run it periodically (e.g. at session end using `SessionSummarizer`) rather than on every message.

---

## Constraints and gotchas

- **All pipelines require a `MemoryStore`** implementing the interface from `pirn.domains.agents.knots`. Any vector store adapter works.
- **`WorkingMemoryPipeline(window_size=N)` counts messages, not tokens.** For LLMs with tight context limits, set `window_size` conservatively.
- **`SemanticMemoryUpsert` compares new facts by embedding similarity.** Set `similarity_threshold` to control how aggressively it deduplicates. Default is `0.95`.
- **`EpisodicMemoryPipeline` writes the episode after the LLM call** — the current run's response is included in the stored episode.

---

## Quick reference

| Memory type | Pipeline | Use for |
|-------------|---------|---------|
| Working | `WorkingMemoryPipeline` | Recent conversation history (in-context window) |
| Episodic | `EpisodicMemoryPipeline` | Past interaction recall by similarity |
| Semantic | `SemanticMemoryPipeline` | Long-term factual knowledge from interactions |
| Procedural | `ProceduralMemoryPipeline` | User preferences and learned action patterns |
| Session summary | `SessionSummarizer` | Compress a session before long-term storage |

---

*See also: [specializations AGENTIC_USE.md](../AGENTIC_USE.md)*
