# Phase 2 Plan — Resolve Residual Inter-Domain Edges (SCD-08, 09, 10)

**Fidelity:** SKELETON ⚠ (item/deps/AC stable from `FEATURES.md`).
**Inherits:** [PIPELINE.md](./PIPELINE.md) A–D.
**Depends on:** SCD-05 (core `pirn.connectors`/`pirn.core` surfaces exist to relocate providers into).
**Issues:** [#59](https://github.com/snoodleboot-io/pirn/issues/59), [#60](https://github.com/snoodleboot-io/pirn/issues/60), [#61](https://github.com/snoodleboot-io/pirn/issues/61).

## Items & dependencies
```
SCD-08 (break agents→ml: EmbeddingProvider → pirn.core.providers) ┐
SCD-09 (break health→agents: LLMProvider+Tool → pirn.core.providers) ┘ → SCD-10 (acyclic-DAG CI gate)
```
**SCD-08 and SCD-09 are genuinely parallel** — different source files, different edges. They fan out concurrently (worktree-isolated); SCD-10 aggregates both.

## Delta §3 — Environment
uv + light docker (providers are pure-abstract; their relocation is import-graph work, not backend I/O). Provider concrete subclasses' tests may need agents/ml extras but no live services. Mostly uv-only.

## Delta §4 — Execution map
```mermaid
flowchart TD
    ENV[Env-Setup: uv sync] --> FAN{fan-out}
    FAN --> S8["SCD-08 (refactor): move EmbeddingProvider (subclasses PirnOpaqueValue)<br/>ml/embedding_provider.py → pirn.core.providers · repoint ml impls + ~5 agents RAG files"]
    FAN --> S9["SCD-09 (refactor): move LLMProvider (+Tool/FunctionTool if coupled)<br/>→ pirn.core.providers · repoint health clinical_nlp_extractor + agents LLM providers"]
    S8 --> AGG{{no agents→ml edge · no health→agents edge · concrete subclasses subclass core base · no behavior change}}
    S9 --> AGG
    AGG --> S10["SCD-10 (devops): topo-sort CI gate over declared inter-package deps"]
    S10 --> AGG10{{acyclic (C1) · only domain→domain edge = pirn-ml→pirn-data (C3) · ml→data retained not broken}}
    AGG10 --> GATES[G-ENF → G-REV] --> DEC[architect: confirm ADR-3 edge resolution] --> DONE([Phase 2 done])
```

## Delta §5 — Subagents
- **SCD-08** (refactor): relocate `EmbeddingProvider`, re-export on core public surface, repoint ml embedding impls + agents `document_processing`. Assert no residual `agents → ml` import.
- **SCD-09** (refactor): relocate `LLMProvider` (+ `Tool`/`FunctionTool` if they travel with it), repoint health `clinical_nlp_extractor` + agents concrete LLM providers. Assert no residual `health → agents` import.
- **SCD-10** (devops): topo-sort over declared package deps; new domain→domain edge fails build pending ADR amendment.

## Delta §7 — Test strategy
ATDD: cross-package import test — `import pirn.core.providers` resolves both bases; importing agents pulls no ml; importing health pulls no agents. TDD: concrete subclasses still satisfy the base contract (behavior unchanged). Acyclic-graph assertion red-before (if a back-edge introduced) / green-after.

## Delta §8 — Integration verification
Build the (still in-tree) packages and run the import-graph check on **real** module imports, not a static grep alone — confirm the two edges are gone at runtime and `pirn-ml → pirn-data` is the sole remaining domain→domain edge.

## Delta §9 — Gaps
- P2-A: whether `Tool`/`FunctionTool` are tightly coupled enough to co-relocate is a judgment call → SCD-09 subagent must *demonstrate* the coupling before moving them (understand-before-applying), else leave them and flag.

## DoD (→ #59/#60/#61 AC)
- ☐ `EmbeddingProvider` in `pirn.core.providers`; agents RAG imports from core; ml impls subclass core base; no agents→ml edge. *(SCD-08)*
- ☐ `LLMProvider` (+co-relocated Tool) in core; health imports from core; agents providers subclass core base; no health→agents edge. *(SCD-09)*
- ☐ CI fails on any cycle; asserts sole domain→domain edge = `pirn-ml→pirn-data`; ml→data retained. *(SCD-10)*
