`pirn_agents.memory.patterns` provides pipelines for the four memory types used in agent systems — it does not store data itself; all persistence goes through a `MemoryStore` (vector store) and optionally a structured database pool.

---

## Mental model

The four memory types map to how humans organize knowledge:
- **Working memory** — recent messages in the current session; stored in-context as a sliding window
- **Episodic memory** — records of past events (what happened, when, outcome); retrieved by similarity
- **Semantic memory** — factual knowledge extracted from interactions; deduplicated and upserted
- **Procedural memory** — learned action sequences and preferences; retrieved to guide decisions

Each type has a `*Pipeline` (a `SubTapestry` over one or two inner knots) and the inner knots themselves, usable directly. Writing and reading are separate knots: the pipelines write, `EpisodicMemoryRetriever` reads. Mix types as needed — most production agents use working + episodic at minimum.

---

## Source map

```
pirn_agents/memory/patterns/
│
│  ── Working memory ──
├── working_memory_pipeline.py        WorkingMemoryPipeline       — append a message to the session window; return the trimmed window
├── working_memory_window_writer.py   WorkingMemoryWindowWriter   — read "working:<session_id>", append, trim to max_size, write back
│
│  ── Episodic memory ──
├── episodic_memory_pipeline.py       EpisodicMemoryPipeline      — store a conversation episode; return its key
├── episodic_episode_writer.py        EpisodicEpisodeWriter       — serialise messages and store them as one episode
├── episodic_memory_retriever.py      EpisodicMemoryRetriever     — search the store for the top_k episodes matching a context
│
│  ── Semantic memory ──
├── semantic_memory_pipeline.py       SemanticMemoryPipeline      — extract facts from messages via an LLM; store them
├── semantic_fact_extractor.py        SemanticFactExtractor       — LLM extracts one fact per line from the conversation
├── semantic_fact_writer.py           SemanticFactWriter          — store each fact under a "semantic:<sha1>" key
├── semantic_memory_upsert.py         SemanticMemoryUpsert        — extract facts from an AgentResponse; record only new ones in a KeyedLineageStore
│
│  ── Procedural memory ──
├── procedural_memory_pipeline.py     ProceduralMemoryPipeline    — record a (task, response) recipe
├── procedural_memory_writer.py       ProceduralMemoryWriter      — store the recipe under a "procedure:" key
│
│  ── Shared ──
└── session_summarizer.py             SessionSummarizer           — summarize messages via an LLM once they exceed token_threshold
```

---

## Canonical pattern

### Working + episodic memory for a conversational agent

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry
from pirn_agents.memory.patterns.episodic_memory_retriever import EpisodicMemoryRetriever
from pirn_agents.memory.patterns.working_memory_pipeline import WorkingMemoryPipeline
from pirn_agents.types.messaging.agent_message import AgentMessage

with Tapestry() as t:
    user_message = Parameter("user_message", AgentMessage)
    user_query = Parameter("user_query", str)
    window = WorkingMemoryPipeline(
        new_message=user_message,
        session_id="session-42",
        store=session_store,
        max_size=20,
        _config=KnotConfig(id="working-mem"),
    )
    episodes = EpisodicMemoryRetriever(
        context=user_query,
        store=episodic_store,
        top_k=3,
        _config=KnotConfig(id="episodic-mem"),
    )
    # feed `window` (tuple[AgentMessage, ...]) and `episodes` into your LLM call knot
```

### Extract and persist semantic facts after a session

```python
from pirn_agents.memory.patterns.semantic_memory_pipeline import SemanticMemoryPipeline

with Tapestry() as t:
    session_messages = Parameter("session_messages", tuple)
    SemanticMemoryPipeline(
        messages=session_messages,
        llm=my_llm,
        store=knowledge_store,
        _config=KnotConfig(id="learn"),
    )
```

---

## Anti-patterns

**Using working memory as long-term storage** — working memory is a bounded window; it evicts old messages as the window fills. Use episodic or semantic memory for anything that must persist beyond the current session.

**Running `SemanticMemoryPipeline` on every turn** — fact extraction is an LLM call. Run it periodically (e.g. at session end) rather than on every message.

---

## Constraints and gotchas

- **The pipelines require a `MemoryStore`** (`pirn_agents.memory.stores.memory_store.MemoryStore`). `SemanticMemoryUpsert` is the exception: it writes to a `KeyedLineageStore` (`pirn_agents.memory.stores.keyed_lineage_store.KeyedLineageStore`).
- **`WorkingMemoryPipeline(max_size=N)` counts messages, not tokens.** For LLMs with tight context limits, set `max_size` conservatively or add a `SessionSummarizer`.
- **`SemanticMemoryUpsert` deduplicates by fact identity, not by embedding similarity.** A fact's identity is the content hash of its text, so only an identical fact is skipped; paraphrases are stored again.
- **`EpisodicMemoryPipeline` stores the messages you pass it** — wire it after the reply is appended if the stored episode must include the reply.

---

## Quick reference

| Memory type | Pipeline | Use for |
|-------------|---------|---------|
| Working | `WorkingMemoryPipeline` | Recent conversation history (in-context window) |
| Episodic | `EpisodicMemoryPipeline` | Store past interactions; recall them with `EpisodicMemoryRetriever` |
| Semantic | `SemanticMemoryPipeline` | Long-term factual knowledge from interactions |
| Procedural | `ProceduralMemoryPipeline` | User preferences and learned action patterns |
| Session summary | `SessionSummarizer` | Compress a session before long-term storage |

---

*See also: [pirn_agents AGENTIC_USE.md](../../AGENTIC_USE.md)*
