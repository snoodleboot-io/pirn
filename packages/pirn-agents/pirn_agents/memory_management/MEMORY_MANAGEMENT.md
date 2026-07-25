# Advanced Memory Management (PAE-F27)

Memory *lifecycle* on top of the F4 stores and `memory_patterns/`: consolidation,
decay/forgetting, cross-session profiles, ranked recall, and the typed record +
provenance schema they all share. Backend-free — every strategy (summarizer,
reranker, store) is caller-injected; the defaults are pure-python.

## Source map

```
pirn_agents/memory_management/
│
│  ── S5 Typed records + provenance (foundation) ──
├── memory_kind.py                  MemoryKind (Literal) + is_memory_kind()
├── memory_provenance.py            MemoryProvenance   — source/timestamp/trust/derivation
├── memory_record.py                MemoryRecord       — typed record; to_payload/from_payload
├── typed_memory_validator.py       TypedMemoryValidator — schema gate (knot)
├── typed_memory_writer.py          TypedMemoryWriter    — write typed record via MemoryStore (knot)
│
│  ── S1 Consolidation (episodic → semantic) ──
├── near_duplicate_grouper.py       NearDuplicateGrouper       — token-Jaccard clustering
├── conflict_resolution_policy.py   ConflictResolutionPolicy   — winner-selection interface
├── recency_trust_conflict_policy.py RecencyTrustConflictPolicy — most-recent, then most-trusted
├── memory_consolidator.py          MemoryConsolidator         — dedup+summarize (knot, uses F17 Summarizer)
│
│  ── S2 Decay / forgetting + eviction ──
├── decay_function.py               decay_score()              — importance x half-life recency
├── decay_scorer.py                 DecayScorer                — per-record decayed value (knot)
├── memory_eviction_policy.py       MemoryEvictionPolicy       — eviction interface
├── ttl_eviction_policy.py          TtlEvictionPolicy          — expire older than TTL
├── low_value_eviction_policy.py    LowValueEvictionPolicy     — drop lowest-value beyond capacity
├── memory_evictor.py               MemoryEvictor              — apply policy + store.forget (knot)
│
│  ── S3 Cross-session profiles ──
├── profile_key.py                  ProfileKey                 — subject-scoped key (F14 seam)
├── entity_profile.py               EntityProfile              — durable per-subject state
├── profile_merge.py                merge_profile_fields()     — deep merge, no clobber
├── cross_session_profile_updater.py CrossSessionProfileUpdater — load/merge/persist (knot)
│
│  ── S4 Ranked recall ──
├── recall_weights.py               RecallWeights              — relevance/recency/importance weights
├── recall_candidate.py             RecallCandidate            — record + raw relevance
├── ranked_memory.py                RankedMemory               — scored result + components
└── ranked_recall.py                RankedRecall               — weighted fusion + optional F4 rerank (knot)
```

## Typed schema + provenance contract (for F11 trust)

Every managed memory is a `MemoryRecord`:

| field           | type                | meaning                                            |
|-----------------|---------------------|----------------------------------------------------|
| `id`            | `str`               | store key                                          |
| `kind`          | `MemoryKind`        | `episodic` / `semantic` / `procedural` / `profile` |
| `content`       | `str`               | text payload                                       |
| `provenance`    | `MemoryProvenance`  | origin + trust (below)                             |
| `created_at`    | `datetime`          | creation time (recency anchor when unaccessed)     |
| `importance`    | `float` in `[0,1]`  | caller-assigned; survives decay, ranks higher      |
| `last_accessed` | `datetime \| None`  | last read; overrides `created_at` as recency anchor |
| `metadata`      | `Mapping`           | scalar extras (e.g. `session_id`, `source_ids`)    |

`MemoryProvenance` is the **soft F11 tie** — a value object F11 trust consumes
without this package depending on F11:

| field          | type               | meaning                                              |
|----------------|--------------------|------------------------------------------------------|
| `source`       | `str` (non-empty)  | producing subsystem/tool                             |
| `timestamp`    | `datetime`         | capture time (recency + conflict tie-break)          |
| `trust_signal` | `float` in `[0,1]` | confidence; F11's trust hook                         |
| `derivation`   | `str \| None`      | how a derived record was made (`consolidated-from:…`) |

Consolidation stamps `derivation="consolidated-from:<sorted source ids>"` and
carries the conflict winner's `trust_signal`, so a consolidated semantic fact is
fully traceable to its episodic sources.

### Migration path (leaves `MemoryStore` unchanged)

`MemoryRecord.to_payload()` / `from_payload()` round-trip a record through the
untyped `MemoryStore` mapping interface. Existing `memory_patterns/` stores keep
reading and writing plain mappings; producers gain a typed, validated view by
routing writes through `TypedMemoryWriter` and validating with
`TypedMemoryValidator`. No store schema changes.

## F14 seam (cross-session profiles)

`ProfileKey.session_id` is a plain optional string — the documented plug point
for **F14 durable sessions (Phase 4, not merged)**. Profiles are keyed by
`storage_key = "profile:<namespace>:<subject_id>"`, which is *session-independent*,
so a profile already survives and accumulates across sessions today. When F14
lands, its session identity/lifecycle supplies `session_id` here without changing
`storage_key`. Nothing in this package invents F14's session machinery.

## How the reuse seams connect

- **S1 → F17.** `MemoryConsolidator` summarizes each near-duplicate group through
  the F17 `Summarizer` interface (`pirn_agents/context/summarizer.py`) — the same
  provider-neutral seam `SummaryMemoryCompactor` uses — turning episodic turns
  into one consolidated semantic record.
- **S4 → F4.** `RankedRecall` fuses each candidate's F4 retrieval relevance with
  recency + importance; its optional `reranker` is the F4
  `RerankerBackend` protocol (`pirn_agents/rerank/reranker_backend.py`), so any
  cross-encoder / LLM scorer / stub is interchangeable and no vendor is favoured.
