# Review: Split Core and Domains (Plan Review)

**Reviewer:** review-agent (principal engineer / plan review)
**Date:** 2026-06-09
**Scope reviewed:** `PRD.md`, `ADR.md`, `FEATURES.md`, `PACKAGING_MIGRATION.md`, `IMPORT_MIGRATION.md`
**Nature:** Planning review only. Validates internal consistency, completeness vs. the agreed decisions, registry/discovery soundness, residual-edge closure, blast-radius adequacy, and FEATURES dependency-correctness. Claims that are load-bearing were re-verified against `sweet_tea` source and the `pirn/domains/` tree.

---

## Verdict: **Ready-with-changes**

The plan is unusually thorough and internally well cross-referenced. The packaging model, connectors fold, edge resolution, blast-radius strategy, and CI rework are coherent and the FEATURES sequencing is genuinely dependency-correct. **However, there is one BLOCKER**: the ADR's central justification for the registry strategy (ADR-4 R1) rests on a factual claim — "knot class names are already globally unique across domains" — that is **false**, and the plan therefore never resolves five real cross-domain key collisions. This does not invalidate R1 (the collisions exist in the monolith today), but the plan's reasoning is wrong and the resolution is missing. Two MAJOR issues (a broken import idiom repeated in code samples; a stale/contradicted ADR dependency-graph description) and several MINORs round it out. None require re-architecting — they require correcting claims and adding two acceptance criteria. Hence Ready-with-changes, not Needs-rework.

---

## Blockers (must fix before execution starts)

### B1 — ADR-4's "globally unique knot class names" premise is false; 5 real cross-domain key collisions are unresolved
**Where:** `ADR.md` ADR-4 ("multiple packages registering distinct knot class names under one library **coexist** without collision … knot class names are already globally unique across domains today"); `PRD.md` Risk #1; `FEATURES.md` SCD-01 AC line 3.

**What is wrong:** Verified against `sweet_tea` source and the domain tree:
- `Registry.register()` de-dups by **full `Entry` equality** `(key, class_def, library, label)`, *not* by `(library, name)` as the ADR states. Two *distinct* classes sharing a lowercased key under the same `library="pirn"` produce **two** entries.
- `AbstractInverterFactory[Knot].create(ref)` (the bare-name YAML path, `pirn/yaml_loader/loader.py:355`) is called with **no `library` filter**. `_create_from_entries` (`inverter_factory.py:126`) raises `SweetTeaError("…did not return a unique result. A total of N possible entries…")` when >1 entry shares the key.
- There are genuine **Knot-subclass** key collisions across domains *today*: `bandpassfilter`, `notchfilter`, `databaseconnectionpoolknot`, `messagebrokerknot`, `freshnesscheck`. (Plus opaque-value collisions like `signalframe`, `signalpayload` shared by signal+health.) `BandpassFilter(Knot)` exists in both `health/eeg_meg/` and (signal/oilgas); `SignalFrame(PirnOpaqueValue)` is a *distinct* class in both `signal/types/` and `health/types/`. None set a disambiguating `label`.

**Why it's a blocker:** ADR-4 is explicitly "the highest-risk decision," and SCD-01 is the architectural gate for the whole initiative. The gate is being justified on a premise that is demonstrably untrue. The good news: because the monolith *already* registers all of these under one `library="pirn"`, R1 does not regress behaviour — the ambiguity is pre-existing and presumably tolerated only because these specific keys are never resolved by bare name in YAML. But the plan must (a) stop asserting uniqueness, and (b) state the actual resolution rule for collided keys.

**Concrete fix:**
1. Correct the ADR-4 text: the registry keys by full Entry tuple, and bare-name resolution raises on >1 entry. Replace "globally unique" with the verified fact: *"≥5 lowercased knot keys already collide across domains under today's single `library='pirn'`; bare-name resolution of a collided key raises `SweetTeaError` today and will continue to under R1 — R1 does not regress this."*
2. Add a resolution decision for the collided keys. Options to evaluate (architect picks): (i) confirm-and-document that these keys are never bare-name-referenced (audit YAML + examples; make it a CI assertion), (ii) assign per-domain `label=` at `fill_registry` time so collided keys disambiguate by label, or (iii) rename the colliding knots. Note current ground-truth: a repo-wide grep found **zero** `callable:`/bare-name YAML references to the colliding keys, which makes option (i) viable — but that must be asserted in CI, not assumed.
3. Strengthen SCD-01 AC: the spike must explicitly reproduce a *real* cross-domain collision (e.g. import two packages that both register `bandpassfilter`) and record the exact `create()` behaviour, then confirm the chosen resolution (i/ii/iii). The current AC only says collision behaviour is "documented" — it must be *resolved*, because a collided key is a latent runtime crash, not a doc note.

---

## Major issues

### M1 — Broken `from sweet_tea import Registry` idiom in every registration/shim code sample
**Where:** `ADR.md` ADR-4 sample (`from sweet_tea import Registry`); `IMPORT_MIGRATION.md` §5 shim sample uses `importlib` so is fine, but the ADR-4 self-registration template and the shim discussion both model the bad import.

**What is wrong:** The installed `sweet_tea/__init__.py` is **empty** (license header only). `from sweet_tea import Registry` raises `ImportError` (verified: `cannot import name 'Registry' from 'sweet_tea'`). The real, working idiom — used by the actual `pirn/__init__.py:44` — is `from sweet_tea.registry import Registry` and `from sweet_tea.sweet_tea_warning import SweetTeaWarning`. Every per-domain `__init__.py` the plan tells executors to write copies the broken form.

**Why it matters:** This is the literal code each of SCD-11…16 will paste into six new package `__init__.py` files. Shipped as-is, every domain package fails to import.

**Fix:** Replace `from sweet_tea import Registry` → `from sweet_tea.registry import Registry` in the ADR-4 template and anywhere else the top-level form appears. Add the correct idiom to the SCD-11…16 extraction template (FEATURES note (b)).

### M2 — ADR-1 dependency-graph prose contradicts ADR-3 / FEATURES on `agents`
**Where:** `ADR.md` ADR-1 ASCII graph caption: "pirn-agents (→core)" — correct — but the same ADR-1 block's "Package dependency graph (after ADR-3 edge resolution)" diagram draws only `pirn-ml → pirn-data` as retained, while the prose two paragraphs above the diagram still lists the *pre-resolution* counts. More concretely: the **PRD Target Package List** (PRD.md table) still shows `pirn-agents` depending on `pirn-core, pirn-ml` and `pirn-health` on `pirn-core, pirn-agents` — i.e. the *unbroken* graph — whereas ADR-3 **breaks** both edges (`EmbeddingProvider`/`LLMProvider` → core), leaving agents→core and health→core only.

**What is wrong:** PRD §Target Package List and §Residual Edges present the "declare the dependency" graph as the table's source of truth ("valid as drawn"), then say the architect *may* break the edges. The ADR *did* break them. The PRD table is now stale: it overstates the dependency surface (`pirn-agents → pirn-ml`, `pirn-health → pirn-agents`) that the accepted ADR eliminates. A reader using the PRD table to write `pyproject.toml` deps would add two edges the ADR forbids (and SCD-10/C3 would then fail the build).

**Why it matters:** PRD and ADR disagree on the final package graph — the single most important output of the whole initiative. PACKAGING_MIGRATION.md §0 and §3 correctly show the *broken* graph (agents→core, health→core), so the PRD is the lone outlier, but it is the document executors will read first.

**Fix:** Update the PRD Target Package List `Depends on` column: `pirn-agents → pirn-core` (drop `pirn-ml`), `pirn-health → pirn-core` (drop `pirn-agents`). Add a one-line note "final graph per ADR-3: every domain → core, plus `pirn-ml → pirn-data`." Keep the Residual Edges section's discussion but mark the ADR's resolution as accepted, not optional.

---

## Minor issues

### m1 — Phase-3 critical path omits `pirn-data` ordering for the `agents` build
`FEATURES.md` Delivery Sequence shows `SCD-15 (agents)` depending on `SCD-08, SCD-13`. SCD-13 is `data`. After ADR-3 breaks `agents→ml`, agents depends only on core — so why gate agents on `data` (SCD-13)? The dependency looks vestigial (left over from when agents→ml→data). Either justify it (e.g. shared test fixtures) or drop SCD-13 from SCD-15's deps so agents can parallelize earlier. Low risk, but it understates available parallelism.

### m2 — `pirn-ml` extras list: `numpy` is both a core hard dep and an ml extra
`PACKAGING_MIGRATION.md` §3a lists `numpy>=2.4.4` as a **hard** dep of `pirn-core` (for the conditional serializer), while PRD §Per-Package Dependency Mapping and §3b put `numpy` inside the `ml` extra. If core hard-depends on numpy, the PRD's "numpy stays *conditional* in the serializer (registered only if importable)" is misleading — it will *always* be importable because core forces it. Reconcile: either numpy is a hard core dep (then drop the "conditional" framing and remove numpy from the ml extra as redundant) or it stays conditional (then it must *not* be a hard core dep). This affects install-isolation assertions (SCD-25 checks "scipy/pywavelets/librosa and nothing else" for signal — numpy would now always be present via core).

### m3 — Shim "deep submodule import" limit may understate internal breakage
`IMPORT_MIGRATION.md` §5 correctly notes the PEP 562 `__getattr__` shim only resurrects `import pirn.domains.data` / `from pirn.domains import data`, **not** `from pirn.domains.data.sources.x import Y`. Given §1's ground truth that **every** internal reference is the deep `from pirn.domains.X.… import …` form (4655 hits, zero bare `import pirn.domains.X`), the shim covers essentially **none** of the historical *internal* call-site shapes — only the rare root-attribute form external consumers might use. This is acknowledged but its consequence should be stated plainly in ADR-5: the shim is a *thin* external courtesy, not a meaningful back-comat layer for the dominant import shape. External consumers doing deep imports (the common case) get `ModuleNotFoundError` even *during* the deprecation window. Consider whether Option C (`pirn[all-domains]` meta) needs to also re-export deep paths, or explicitly document that deep-import consumers must run the codemod immediately (no soft landing).

### m4 — `extras_loader.py` ownership undecided across docs
`ADR.md` ADR-4 adjacent-fixes and `IMPORT_MIGRATION.md` §6 both say `extras_loader.py` "moves with the domains; one copy per domain package, **or** a shared core copy." This is left open across two docs. Six copies risks drift; one core copy means core grows a domain-facing helper. Pick one (core copy is cleaner and matches the connectors-in-core direction) so SCD-06/SCD-11…16 don't each re-decide it.

### m5 — `pytest.ini` claim about `[tool.pytest.ini_options]` validity is asserted, not verified
`PACKAGING_MIGRATION.md` §4 states "`[tool.pytest.ini_options]` is not valid on a non-project root → move it to a root `pytest.ini`." The root *is* still a valid TOML file with `[tool.uv.workspace]`; pytest reads `[tool.pytest.ini_options]` from any `pyproject.toml` it discovers, regardless of whether that file declares `[project]`. This may be a non-issue; verify before mandating a `pytest.ini` split (cheap to confirm, avoids an unnecessary config file).

### m6 — SCD-01 spike outcome can invalidate downstream issues but no contingency is documented
SCD-01 is correctly gated first, but FEATURES/ADR present R1 as already-resolved ("Verified by source read"). If the spike surfaces the B1 collision behaviour as blocking (it will, for the 5 collided keys if any are bare-name-referenced), there is no documented fallback path (R2 library-qualified, or label-based disambiguation) wired into the issue graph. Add a one-line contingency to SCD-01: "if collided keys are bare-name-referenced, adopt label-based disambiguation (amend ADR-4); else assert-and-proceed."

---

## What is solid (validated, no change needed)

- **Connectors fold (ADR-2):** correctly identified as infra-not-domain; the "no backend dep at core import time" contract (C2) is the right enforcement and is operationalized in SCD-07. The conditional-numpy template is the right model (modulo m2).
- **Edge resolution (ADR-3):** the break/declare reasoning is sound — abstract interfaces (`EmbeddingProvider`, `LLMProvider`) to core, concrete `DataBatch` stays in data with a declared `ml→data` edge. Verified these symbols exist where claimed and `data` does not import `ml` (so the retained edge is acyclic). Resulting "tree + one edge" graph is correct.
- **FEATURES topological order:** `signal → oilgas → data → ml → agents → health` is dependency-correct; `ml after data` (SCD-14 ← SCD-13) and `ml after EmbeddingProvider move` (SCD-14 ← SCD-08) are right. Critical path is accurate (modulo m1).
- **Codemod strategy (IMPORT_MIGRATION):** ast-grep-for-imports + hand-edit-for-strings + incremental-per-PR is the correct call; the connectors-special-case (rule 0, `pirn.connectors` not `pirn_connectors`) and the symbol-aware exclusion of the two break-edge symbols from the bulk pass are well-reasoned and avoid the obvious foot-guns. Verified: 0 bare `import pirn.domains.X`, 0 dynamic `import_module("pirn.domains…")`, so the "single grammatical shape" claim holds.
- **CI/packaging (PACKAGING_MIGRATION):** the 192-job mitigation (per-package lint/build + whole-workspace test + change-detection) correctly preserves the cross-domain registry-parity test that a naive per-package test split would break. Lockstep-then-independent versioning and `pirn-core`-first publish ordering are correct.
- **Blast-radius window (ADR-5):** B→A with opt-in C is reasonable; deprecation-warning test is specified.

---

## Required changes summary (for the architect)

| Pri | Item | Action |
|-----|------|--------|
| BLOCKER | B1 | Correct ADR-4 registry-keying/uniqueness claims; resolve the 5 cross-domain key collisions (audit-and-assert / label / rename); strengthen SCD-01 AC to *resolve* not just document. |
| MAJOR | M1 | Fix `from sweet_tea import Registry` → `from sweet_tea.registry import Registry` in all registration/shim samples and the SCD-11…16 template. |
| MAJOR | M2 | Update PRD Target Package List to the ADR-3 *broken-edge* graph (agents→core, health→core). |
| minor | m1–m6 | Resolve agents/data vestigial dep; reconcile numpy core-vs-ml; clarify shim deep-import limit; fix extras_loader ownership; verify pytest.ini claim; add SCD-01 contingency. |

Re-review only B1's resolution and M1/M2 corrections is required before unblocking SCD-01 → SCD-02.
