# ADR: WS5 Taxonomy — flat root → domain subpackages (Phase 5 / Wave 1)

**Status:** Accepted (frozen contract). Landed incrementally by story lanes S1–S7.
**Nature:** behavior-preserving moves/renames only. No logic changes. Every target obeys
one-class-per-file + `filename == snake_case(ClassName)`. `pirn-core` is immutable — referenced,
never edited.

This ADR is the frozen taxonomy the WS5 story lanes (S1–S7) consume. It records the target
tree, the four rulings, the per-story old→new manifests, and the required lane ordering.

Package base (abbreviated `…/` below):
`packages/pirn-agents/pirn_agents/`

Target model = **CORE-PARITY**: the package root holds ONLY `__init__.py` + a cross-cutting
entrypoint. Core reserves its root for `__init__` + `domain_discovery`/`replay`/`tapestry` and
nests knots under their domain (`pirn/connectors/knots/`, NOT a top-level `pirn/knots/`). We mirror
that: knots live in a `knots/` subpackage **nested inside their domain**, not a flat top-level dir.

---

## 1. THE FOUR RULINGS

### Ruling 1 — Tool-framework home: **REUSE `tools/` (do NOT rename to `tooling/`)**
- **Verified zero filename collisions.** A `find` across the whole `tools/` tree for all 13 root
  `tool*.py` names returned nothing — in particular there is **no `tools/tool.py`**, so the
  framework base `Tool` (root `tool.py`) lands cleanly.
- `tools/base_tool.py` (`BaseTool(Tool)`) **already imports** root `pirn_agents.tool.Tool`; moving
  `tool.py` into `tools/` turns an upward dependency into a same-package sibling import (net
  improvement).
- `tools/` today is the concrete "batteries" catalog (calculator/, filesystem/, web/, sql/, sandbox/,
  retrieval/, `bundles.py`). Merging the framework makes `tools/` mean "framework + batteries," which
  is core-parity-consistent (root reserved for `__init__`).
- Renaming to `tooling/` was a strawman: core has no `tooling` package to mirror, and a rename would
  churn ~34 existing files + every concrete-tool importer for zero structural gain.
- **Consequence:** the 13 framework modules AND the three S6 tool value objects (`ToolCall`,
  `ToolResult`, `ToolStatus`) fold into `tools/`. This unblocks S1 and S6.

### Ruling 2 — `connectors/` already exists → **S1 folds glue INTO it, creates nothing new**
- `connectors/` holds `column_aware_pool*.py`, `http_search_connector.py`, `sql_service_connector.py`,
  `streaming_s3_store.py`. Only `connector_lifespan.py` moves in (teardown helper for these pools).
- **Correction to the brief's guess:** `provider_adapter.py` and `llm_provider.py` are NOT connector
  glue — they are LLM-layer types and route to `llm/` (see §3, group llm/).

### Ruling 3 — Branch prefix: **`feat/PIR-<id>-<desc>`** (kebab, ≤60 chars)
- Use `feat/` (house rule), NOT Linear's `feature/`. e.g. `feat/PIR-698-root-modules-to-domains`.

### Ruling 4 — Knot count: **8 knots, not 9 — proceed with the 8 that exist**
- Only 8 root `*_knot.py` exist; **there is no `blob_store_knot.py`**. Git history:
  `blob_store_knot.py` existed (F16/PIR-30, `cc6a8f5`) and was **deleted** in
  `0fd4488`/`bacf448` — *"refactor(connectors): delete BlobStore, depend on core ObjectStore
  (WS3·S2 / PIR-690)"*. The slot migrated to core's `connectors/knots/object_store_knot.py`.
  The S2 ticket's "9" is stale; a stale `__pycache__/blob_store_knot.*.pyc` is the only residue
  (zero source references). **No action for the phantom 9th.**

---

## 2. TWO BOUNDARY-OVERLAP RESOLUTIONS (one owner per path — no lane collides)

### (a) `specializations/memory_patterns/` → **owned by S3 (memory umbrella)**
- Both the memory mapper and the specializations mapper confirm: the package contains **no
  `AgentResult`/`AgentPipeline`-style bases** — only `Knot` stages + `SubTapestry` memory pipelines
  (episodic/semantic/procedural/working). It is pure memory-pattern code.
- **Zero cross-lane importers** — nothing outside the package (bar tests) imports it, so moving it
  severs no specialization consumer.
- **Ruling:** S3 moves it to `memory/patterns/`. S5 excludes it. S5's package count drops by 1
  (flag to S5 owner; no code coupling to cut).

### (b) `vector_store_knot.py` + `embedding_provider_knot.py` → **owned by S4 (retrieval umbrella)**; `memory_store_knot.py` → **owned by S3**
- The two mappers split on these. Resolution rule: **the lane that BUILDS the destination package
  tree owns the knot move**, so no two lanes ever write the same path.
- S4 creates `retrieval/vector_stores/` and `retrieval/embeddings/`; therefore S4 places
  `vector_store_knot` → `retrieval/vector_stores/knots/vector_store_knot.py` and
  `embedding_provider_knot` → `retrieval/embeddings/knots/embedding_provider_knot.py`. **S2 does NOT
  touch these two.**
- S3 creates `memory/stores/`; therefore S3 places `memory_store_knot` →
  `memory/stores/knots/memory_store_knot.py`. **S2 does NOT touch it.**
- **S2's actual slice = the 5 knots whose domains are not restructured into umbrellas:**
  `connectors/knots/{http_connector_knot,search_connector_knot,sql_connector_knot}.py`,
  `llm/knots/llm_provider_knot.py`, `tools/knots/tool_client_knot.py`.
- Registration is safe: all 8 are genuine `Knot` subclasses; discovery is name-based tree-walk
  (`Registry.fill_registry`) + construction-time tapestry self-register — relocation anywhere in
  `pirn_agents/` preserves registration provided class names are unchanged (they are) and each new
  `knots/` dir gets an `__init__.py`.

---

## 3. TARGET TOP-LEVEL TREE (after all of WS5)

```
pirn_agents/
├── __init__.py                 # re-exports + Registry.fill_registry (unchanged behavior)
├── capability_probe.py         # KEPT AT ROOT — init-time extras entrypoint (parity w/ core replay/tapestry)
├── _internal/                  # NEW — shared private utils
│   └── _require.py             # 34 importers across 9 subpackages; no single domain owner
├── agent/                      # NEW — agent runtime (S1)
├── tools/                      # framework + batteries + tool value objects + tools/knots/ (S1,S6,S2)
├── connectors/                 # + connector_lifespan + connectors/knots/ (S1,S2)
├── llm/                        # + llm_provider, provider_adapter + llm/knots/ (S1,S2)
├── interfaces/                 # NEW — S7 shared NotImplementedError bases (Retriever/Writer/Router)
├── memory/                     # S3 umbrella: memory/{stores,management,patterns}/ (+ stores/knots/)
├── retrieval/                  # S4 umbrella: retrieval/{rerank,vector_stores,embeddings,graph_rag,graph_stores}/
├── types/                      # S6 split → types/{content,messaging}/  (tool VOs leave to tools/)
├── specializations/            # S5: + specializations/base/{agent_result,agent_pipeline}.py ; 21 pattern pkgs
├── planning/                   # + plan.py (from types/, S6)
├── security/                   # + _safe_pattern_compiler.py (S1)
│   … (unchanged: batch, benchmarks, builder, caching, context, control, determinism,
│      evaluation, exceptions, generation, input, mcp, observability, performance, prompt,
│      resilience, sessions, testing, validation)
```
Root after WS5 = `__init__.py` + `capability_probe.py` only. (Alternative considered: move
`capability_probe` to `agent/` and rewrite the one `__init__` import — rejected to minimize churn on
the package init; it is genuinely the extras-probe entrypoint.)

---

## 4. PER-STORY MANIFESTS (old → new)

### S1 / PIR-698 — clear the 29 non-knot root modules into first-level domains
Reserve root for `__init__.py` + `capability_probe.py`. The 8 `*_knot.py` are NOT S1's (see S2/S3/S4).

| old (root) | class / symbol | new path | note |
|---|---|---|---|
| agent_invoker.py | AgentInvoker | agent/agent_invoker.py | |
| agent_introspector.py | AgentIntrospector | agent/agent_introspector.py | |
| agent_schema_deriver.py | AgentSchemaDeriver | agent/agent_schema_deriver.py | |
| agent_response_mapper.py | AgentResponseMapper | agent/agent_response_mapper.py | |
| agent_tool_context.py | AgentToolContext (+2 ctx fns) | agent/agent_tool_context.py | multi-symbol module (contextvar accessors) — accepted |
| async_fanout_engine.py | AsyncFanoutEngine | agent/async_fanout_engine.py | base of ParallelToolExecutor |
| parallel_tool_executor.py | ParallelToolExecutor | agent/parallel_tool_executor.py | keep with its base |
| approval_hook.py | ApprovalHook | agent/approval_hook.py | |
| tool.py | Tool | tools/tool.py | Ruling 1 — no collision |
| tool_registry.py | ToolRegistry | tools/tool_registry.py | |
| toolset.py | Toolset | tools/toolset.py | |
| function_tool.py | FunctionTool | tools/function_tool.py | |
| agent_tool.py | AgentTool | tools/agent_tool.py | agent↔tool seam; lives in tools/ as a Tool |
| as_tool.py | as_tool() | tools/as_tool.py | |
| agent_as_tool_mixin.py | AgentAsToolMixin | tools/agent_as_tool_mixin.py | |
| tool_decorator.py | tool() | tools/tool_decorator.py | |
| tool_call_codec.py | ToolCallCodec | tools/tool_call_codec.py | |
| tool_permissions.py | ToolPermissions | tools/tool_permissions.py | |
| tool_invocation_hook.py | ToolInvocationHook | tools/tool_invocation_hook.py | |
| tool_schema_compiler.py | ToolSchemaCompiler | tools/tool_schema_compiler.py | |
| streaming_tool_call_parser.py | StreamingToolCallParser | tools/streaming_tool_call_parser.py | |
| llm_provider.py | LLMProvider | llm/llm_provider.py | pairs w/ llm_provider_knot |
| provider_adapter.py | ProviderAdapter | llm/provider_adapter.py | NOT connectors — LLM tool-call adapter iface |
| connector_lifespan.py | connector_lifespan() | connectors/connector_lifespan.py | |
| embedding_provider.py | EmbeddingProvider | embeddings/embedding_provider.py | 2-hop: S4 later folds → retrieval/embeddings/ |
| memory_store.py | MemoryStore | memory/memory_store.py | 2-hop: S3 later folds → memory/stores/ |
| _safe_pattern_compiler.py | SafePatternCompiler | security/_safe_pattern_compiler.py | |
| _require.py | _require() | _internal/_require.py | shared private util |
| capability_probe.py | CapabilityProbe | (STAYS at root) | init-time entrypoint; `__init__` untouched |

Group blast radius (importers, mostly tests + `specializations/**`): llm_provider **167**, memory_store
**103**, tool **72**, embedding_provider **45**, toolset 43, _require 34, parallel_tool_executor 17,
_safe_pattern_compiler 18; agent/ group all ≤10 (safest to move first); connector_lifespan 1.

### S2 / PIR-699 — knots (5 only; the other 3 are S3/S4 per §2)
Mirror core's `connectors/knots/`: a `knots/` subpackage nested in each domain (each new dir gets `__init__.py`).

| old (root) | class | new path | owner |
|---|---|---|---|
| http_connector_knot.py | HttpConnectorKnot | connectors/knots/http_connector_knot.py | S2 |
| search_connector_knot.py | SearchConnectorKnot | connectors/knots/search_connector_knot.py | S2 |
| sql_connector_knot.py | SqlConnectorKnot | connectors/knots/sql_connector_knot.py | S2 |
| llm_provider_knot.py | LLMProviderKnot | llm/knots/llm_provider_knot.py | S2 |
| tool_client_knot.py | ToolClientKnot | tools/knots/tool_client_knot.py | S2 |
| memory_store_knot.py | MemoryStoreKnot | memory/stores/knots/memory_store_knot.py | **S3** |
| vector_store_knot.py | VectorStoreKnot | retrieval/vector_stores/knots/vector_store_knot.py | **S4** |
| embedding_provider_knot.py | EmbeddingProviderKnot | retrieval/embeddings/knots/embedding_provider_knot.py | **S4** |

Filenames already equal snake_case(ClassName) — relocation only. Importers are all tests; hottest:
`tests/connectors/test_connector_knots.py` (imports http/search/sql).

### S3 / PIR-700 — memory umbrella (`memory/{stores,management,patterns}/`), one base writer
- `memory_store.py` (from S1's memory/) → `memory/stores/memory_store.py` (THE store iface; 81 importers).
- `memory_store_knot.py` → `memory/stores/knots/memory_store_knot.py`.
- keep at umbrella root: `memory/memory_writer.py`, `memory/memory_retriever.py`, `memory/conversation_buffer.py`.
- `memory_management/*` → `memory/management/*` (25 files: value objects `MemoryRecord`,
  `MemoryProvenance`, `EntityProfile`, `ProfileKey`, `RecallCandidate/Weights`, `RankedMemory`,
  `NearDuplicateGrouper`; policy bases `ConflictResolutionPolicy`, `MemoryEvictionPolicy` + concretes;
  knots `MemoryEvictor/Consolidator`, `DecayScorer`, `RankedRecall`, `CrossSessionProfileUpdater`,
  `TypedMemoryValidator`, `TypedMemoryWriter`; fn-modules `decay_function`, `memory_kind`,
  `profile_merge`; doc `MEMORY_MANAGEMENT.md`).
- `specializations/memory_patterns/*` → `memory/patterns/*` (13 files; §2a).
- **One base writer:** no shared writer exists today — 6 writers all extend `Knot` directly
  (`MemoryWriter`, `TypedMemoryWriter`, `EpisodicEpisodeWriter`, `SemanticFactWriter`,
  `ProceduralMemoryWriter`, `WorkingMemoryWindowWriter`). Consolidate onto the S7 `Writer` base
  (see interfaces/, §S7). `memory/memory_writer.py` is the umbrella-root home for the memory-facing
  Writer. (Red herring: core `connectors/capabilities/record_writer.py::RecordWriter` is a tabular
  connector capability — do NOT adopt.)

### S4 / PIR-701 — retrieval umbrella
Fold five packages under `retrieval/` and carry the two contested knots (§2b):
`rerank/` → `retrieval/rerank/`; `vector_stores/` → `retrieval/vector_stores/`; `embeddings/` →
`retrieval/embeddings/` (incl. S1's `embedding_provider.py`); `graph_rag/` → `retrieval/graph_rag/`;
`graph_stores/` → `retrieval/graph_stores/`.
- Stay at `retrieval/` root (cross-cutting): `bm25_index.py`, `hybrid_retriever.py`,
  `reciprocal_rank_fusion.py` (fn-module).
- Existing domain bases stay in their sub (leave as-is): `VectorMemoryStore` (vector_stores),
  `GraphStore` (graph_stores), `RerankerBackend` (rerank), `BaseEmbeddingProvider` (embeddings).
- Knots (from §2b): `retrieval/vector_stores/knots/vector_store_knot.py`,
  `retrieval/embeddings/knots/embedding_provider_knot.py`.
- High fan-in test bases to migrate first: `tests/vector_stores/conformance.py`,
  `tests/graph_stores/conformance.py`.

### S5 / PIR-702 — AgentResult / AgentPipeline bases for the specialization packages
- **NEW:** `specializations/base/agent_result.py` (`AgentResult`), `specializations/base/agent_pipeline.py`
  (`AgentPipeline`).
- Common surface (verified): all 11 `*Result` are `@dataclass(frozen=True)` subclasses of
  `PirnOpaqueValue` sharing only the `_pirn_audit_dict() -> dict[str, Any]` override (no shared
  fields) → `AgentResult` = frozen `PirnOpaqueValue` marker with a NotImplementedError
  `_pirn_audit_dict`. All Pipelines subclass core `SubTapestry` with the `process(**) -> Knot`
  contract → `AgentPipeline` = `SubTapestry` subclass with the house NotImplementedError `process`.
- **Scope = 21 packages** (22 on disk − `memory_patterns` which leaves to S3). NOTE: ~half the
  packages are `Knot` toolkits with neither a `*Result` nor a `Pipeline` — S5 must not assume both
  exist. Loose module `specializations/llm_response_text.py` is the likely source of the ticket's
  "23"; flag to S5 owner (not a blocker).
- Hottest production consumer to watch on any rename: `builder/agent_pattern_registry.py`.

### S6 / PIR-703 — types split + tool-VO fold + two specialization edits
- **`types/` → `content/` + `messaging/`:**
  - content/: `content_block.py`, `text_block.py`, `image_block.py`, `audio_block.py`,
    `file_block.py`, `media_handle.py`, `message_content.py`, `tool_result_block.py`.
  - messaging/: `agent_message.py`, `agent_context.py`, `agent_response.py`.
- **Tool value objects → `tools/` (Ruling 1):** `types/tool_call.py`→`tools/tool_call.py`,
  `types/tool_result.py`→`tools/tool_result.py`, `types/tool_status.py`→`tools/tool_status.py`.
  Sequence the tool-VO fold **before** the content move: `content/tool_result_block.py`
  (`ToolResultBlock`, a `ContentBlock`) imports `ToolResult`. Import direction stays acyclic:
  messaging → content → tools.
- **Outlier `types/plan.py` (`Plan`) → `planning/plan.py`** (planning-layer value object; not content
  or messaging). RULED here.
- **Extract `_ResponseEcho`:** `specializations/multi_agent/round_robin_review.py` →
  new `specializations/multi_agent/_response_echo.py` (`_ResponseEcho(Knot)`; zero external importers).
- **Rename `specializations/rag/relevance_gate.py` → `relevance_check.py`:** FILE rename only — the
  class is already `RelevanceCheck` (the file was mis-named). Fixes the convention. Update importer
  `corrective_rag_pipeline.py` (path only) + test file; stale docstring in `corrective_router.py`
  is cosmetic.
- Blast radius: `pirn_agents.types` has **294** import lines (AgentResponse 155, AgentMessage 74,
  ToolCall 51, ToolStatus 36, ToolResult 33 …). Hottest: `llm/*multimodal_adapter*` ×3,
  `document_processing/loaders/media_loader.py`, tool-executor/codec/mcp cluster.

### S7 / PIR-728 — shared Retriever / Writer / Router bases (NotImplementedError, NOT Protocol)
- **NEW sibling package `interfaces/`** (bases must not live under any one consumer or memory/ and
  retrieval/ would import "up" into specializations/ — inversion):
  `interfaces/retriever.py` (`Retriever`), `interfaces/writer.py` (`Writer`),
  `interfaces/router.py` (`Router`) — each a `Knot` subclass whose `process` raises
  `NotImplementedError` (mirror the existing `ConsensusStrategy` house pattern).
- **No `typing.Protocol` to replace** — repo has zero runtime `Protocol` bases (only docstrings
  reaffirming the no-Protocol rule). S7 creates fresh bases.
- Implementers to rebase (coordination, not moves): retrievers — `retrieval/hybrid_retriever.py`,
  `retrieval/graph_rag/hybrid_graph_retriever.py`, `memory/memory_retriever.py`, and ~10 in
  `specializations/rag/`; writers — the 6 memory writers (S3); routers — `specializations/routing/*`
  (⚠ `ModelCascadeRouter` is a bare class, NOT a `Knot` — needs a small base-fit change),
  `multi_agent/OrchestratorRouter`, `rag/CorrectiveRouter`, `human_in_the_loop/EscalationRouter`.

---

## 5. CROSS-LANE IMPORTER / COLLISION NOTES — why the waves must sequence

The dominant shared-importer surface is **`specializations/**` and `tests/**`** — nearly every move
is an import-path rewrite in tests, and `specializations/` is the top consumer of `llm_provider`
(167), `memory_store` (103), `embedding_provider` (45), `tool` (72), and `types.AgentResponse` (155).
That single directory is co-edited by S1 (import rewrites), S3, S4, S5, S6, and S7 → it forces the
ordering below. Files touched by multiple lanes:

- `specializations/rag/**` — S1 (import rewrites), S3 (memory_store paths), S4 (retrieval paths),
  S5 (AgentResult/Pipeline bases + 16 pipelines), S6 (relevance_gate rename), S7 (10 retrievers +
  routers). **The hottest collision zone.**
- `specializations/multi_agent/**` — S5 (OrchestratorAgent/Result) + S6 (`_ResponseEcho` extract).
- `builder/agent_pattern_registry.py` — production map name→pipeline; S1 import rewrites + any S5 rename ripples.
- `tests/vector_stores/conformance.py`, `tests/graph_stores/conformance.py` — high fan-in (S4); migrate first.
- `tests/connectors/test_connector_knots.py` — S2 (3 knots at once).
- `llm/base_llm_provider.py`, `llm/*multimodal_adapter*.py` — S1 (llm_provider) + S6 (content types).
- root `__init__.py` — re-exports `CapabilityProbe` + `fill_registry`; **untouched** because
  `capability_probe.py` stays at root (deliberate, to keep S1 off the package init).

**Required ordering (matches the ledger dependency graph):**
1. **S1** — clears root into first-level domains; creates `agent/`, `_internal/`; reserves root.
   Everything else depends on this. No upstream dependency.
2. **S3, S4, S6** (depend on S1) — memory umbrella / retrieval umbrella / types split. Distinct
   package trees; S6 also touches `specializations/{multi_agent,rag}` → flag vs S5.
3. **S2** (depends S1·S3·S4) — 5 knots into `connectors|llm|tools/knots/` (the memory/retrieval
   knots already moved by S3/S4, so no path is double-owned).
4. **S7** (depends S3·S4) — `interfaces/` bases; rebases the retrievers/writers that now exist.
5. **S5** (depends S6·S3·S7) — LAST. `specializations/base/` + rebase 21 packages; runs after the
   types split, memory_patterns extraction, and interfaces bases are all in place.

---

## 6. NOTES
- Both genuinely contentious items — contested-knot ownership and the S7 shared-base home — are
  resolved decisively above (§2b: S4/S3 own contested knots by destination-ownership; §S7: neutral
  `interfaces/` package avoids import inversion).
- Specializations count is 22 dirs on disk → 21 after `memory_patterns` leaves; the S5 ticket's "23"
  is stale (likely counts the loose `specializations/llm_response_text.py`).
