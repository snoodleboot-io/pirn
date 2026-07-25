# Import Migration: `pirn.domains.<x>` → distinct top-level packages

**Status:** Planning — companion to `PRD.md`, `ADR.md`, `FEATURES.md` (this directory)
**Date:** 2026-06-09
**Tracking Issue:** [#51](https://github.com/snoodleboot-io/pirn/issues/51)
**Owning work item:** `SCD-17` (codemod) — also feeds `SCD-21` (examples) and `SCD-23` (consumer tool)
**Scope:** Planning only. This document specifies the codemod/import-rewrite **strategy**. It does **not** move, rename, or rewrite any source this session.

> This file is the mechanical companion to ADR-4 (registry) and ADR-5 (compat shim). It does **not** relitigate those decisions — it specifies *how* the rewrite is executed, *which* tool, *how the tree stays green per phase*, and *how it is verified*. Settled facts (R1 self-registration, B→A shim, lockstep versioning) are treated as inputs.

---

## 1. Ground truth (verified by reading source, 2026-06-09)

These numbers drive every decision below. Counts are line-hits of `pirn.domains.` (re-verify before executing — they are sizing signals, not contractual).

| Location | `pirn.domains.*` hits | Notes |
|----------|----------------------:|-------|
| `pirn/` (source) | ~2140 | includes intra-domain absolute imports |
| `tests/` | ~2921 | mirrors `pirn/` layout; 9 conftests |
| `examples/` | ~21 | 11 example dirs |
| `docs/` | ~115 | prose + embedded code blocks |
| `.github/workflows/ci.yml` | 34 | bash `import pirn.domains.<x>` smoke lines (the only "YAML" hits) |
| tapestry `*.yaml` `callable:` | **0** dotted `pirn.domains` | the 8 `callable:` lines point at `examples.*` user knots, **not** `pirn.domains` |

**Decisive structural facts** (these make the codemod tractable):

1. **Every reference is the `from pirn.domains.X ... import ...` form.** Verified: `from pirn.domains.` = **4655** hits; **bare `import pirn.domains.X` = 0**; **`import pirn.domains.X as Y` = 0**. There is no attribute-access-after-`import pirn` usage to chase. The rewrite is almost entirely a single grammatical shape.
2. **Zero relative imports inside domains.** `from .` / `from ..` inside `pirn/domains/` = **0**. Domains import their own submodules *absolutely* (`from pirn.domains.signal.filters.x import Y`). Consequence: **intra-domain imports must be rewritten too** (`pirn.domains.signal.` → `pirn_signal.`), not just cross-package ones. This is more lines but a *simpler* rule (no relative-vs-absolute branching).
3. **No dynamic dispatch on `pirn.domains` strings.** `importlib.import_module("pirn.domains…")` / `__import__` = **0**. The only string-literal occurrences are 3 human-readable messages (below). The registry/YAML path resolves by **bare knot name**, not by `pirn.domains` dotted path (ADR-4), so the codemod does **not** touch YAML knot references.
4. **`connectors` is the asymmetric case (1255 hits).** Unlike the six domains, connectors **folds into core** (ADR-2), so `pirn.domains.connectors` → **`pirn.connectors`** (stays under the `pirn` import name), *not* `pirn_connectors`. This is the single most common mapping and the one most likely to be mis-rewritten by a naïve `pirn.domains.<x>` → `pirn_<x>` rule. **It must be handled by a dedicated, higher-priority rule.**

---

## 2. Import-path mapping table (old → new)

The rewrite is a longest-prefix match. `connectors` is special and is matched **first**.

| # | Old prefix | New prefix | Applies to | Form after rewrite |
|---|-----------|-----------|-----------|--------------------|
| **0** | `pirn.domains.connectors` | `pirn.connectors` | folded into core (ADR-2) | `from pirn.connectors.object_storage.s3 import S3Store` |
| 1 | `pirn.domains.signal` | `pirn_signal` | standalone domain | `from pirn_signal.filters.x import Y` |
| 2 | `pirn.domains.data` | `pirn_data` | domain | `from pirn_data.data_batch import DataBatch` |
| 3 | `pirn.domains.ml` | `pirn_ml` | domain (→data) | `from pirn_ml.training.x import Y` |
| 4 | `pirn.domains.agents` | `pirn_agents` | domain | `from pirn_agents.control.x import Y` |
| 5 | `pirn.domains.health` | `pirn_health` | domain | `from pirn_health.mri.x import Y` |
| 6 | `pirn.domains.oilgas` | `pirn_oilgas` | domain | `from pirn_oilgas.seismic.x import Y` |
| 7 | `pirn.domains.extras_loader` | `pirn.connectors.extras_loader` **or** per-package copy | shared helper (see §6) | special — see note |
| 8 | `pirn.domains` (bare, e.g. `from pirn.domains import extras_loader`) | depends on target (§6) | 1 known site (`test_domains_extras.py:18`) | rewrite by hand |

**Relocated-symbol overrides (ADR-3 — applied as targeted rules layered on top of the prefix map):**

| Old import | New import | Reason |
|-----------|-----------|--------|
| `from pirn.domains.ml.embedding_provider import EmbeddingProvider` | `from pirn.core.providers import EmbeddingProvider` | edge `agents→ml` broken (ADR-3) |
| `from pirn.domains.agents.llm_provider import LLMProvider` (and co-moved `Tool`/`FunctionTool`) | `from pirn.core.providers import LLMProvider` | edge `health→agents` broken (ADR-3) |
| `from pirn.domains.data.data_batch import DataBatch` *(and `LakehouseTable`/`FileSource`/`SqlSource`)* | `from pirn_data.data_batch import DataBatch` | edge `ml→data` **retained** — normal rule 2, **no** override |

> The two **break** edges (`EmbeddingProvider`, `LLMProvider`) need *symbol-aware* rules, not prefix rules: the same `pirn.domains.ml.*` prefix maps to `pirn_ml` for everything **except** `embedding_provider`, which maps to `pirn.core.providers`. These few symbols are best moved by the relocation PRs (SCD-08/09) themselves and excluded from the bulk codemod, so the codemod stays a pure prefix rewrite. See §4 ordering.

---

## 3. Tool choice for the rewrite

The rewrite is dominated by one syntactic shape (`from pirn.domains.X import …`) with **no** aliasing and **no** dynamic forms, so an AST/CST tool is *not strictly required* for correctness — but it is required for **safety against false positives** in strings/comments and for **idempotency**. Recommendation below, with the rejected options and why.

### Recommended: **`ast-grep` (sg) for the bulk import rewrite + a tiny scripted pass for the 3 string literals**

| Aspect | Why ast-grep wins here |
|--------|------------------------|
| **Targets syntax, not text** | Matches `import`-statement nodes only, so it will **never** rewrite the `"pirn.domains.data.transforms.filter.Filter"` *string literal* in `pyarrow_filter.py` (a `sed` would). |
| **Rule-file driven** | The mapping table §2 becomes a small YAML rule list (one rule per prefix, connectors rule first). Reviewable, version-controlled, re-runnable. |
| **Fast + language-agnostic invocation** | One pass over `pirn/`, `tests/`, `examples/`; trivial to scope per-directory so we run it incrementally per extraction PR (§4). |
| **Idempotent** | Re-running on already-migrated code is a no-op (the `pirn.domains` pattern no longer matches). |

The **3 string-literal messages** (not imports) are rewritten by an explicit, reviewed edit, **not** the AST tool:
- `pirn/domains/extras_loader.py:46` f-string `f"pirn.domains.{self._extra_name} requires…"` → moves with §6.
- `pirn/domains/data/frames/pyarrow/pyarrow_filter.py:92` and `polars/polars_filter.py:75` docstring/error text `"pirn.domains.data.transforms.filter.Filter knot instead"` → `"pirn_data.transforms.filter.Filter knot instead"`.

These three are enumerated by `grep -n '"pirn\.domains\|pirn\.domains\.[a-z]* requires'` and fixed by hand in the relevant extraction PR — too few to automate, too important to miss.

### Alternatives considered

| Tool | Verdict | Trade-off |
|------|---------|-----------|
| **libcst (codemod)** | **Viable runner-up.** | Most precise (full CST, preserves comments/whitespace, can do symbol-aware moves for the ADR-3 break edges in one pass). Cost: heavier to author (a `VisitImportFrom`/`Transformer` per rule), slower, adds a dev dependency. **Choose libcst over ast-grep only if** we decide to fold the EmbeddingProvider/LLMProvider symbol-aware moves into the same automated pass instead of doing them in SCD-08/09. Recommended fallback if ast-grep's string-safety proves insufficient on docs code-blocks. |
| **ruff (isort) `--fix`** | **Not a rewriter.** | Ruff/isort **reorders and groups** imports; it does **not** remap module paths. Useful *after* the codemod to re-sort the new `pirn_<x>` imports into the correct stdlib→third-party→internal groups (general.md import convention) — so it is a **post-step**, not the rewriter. |
| **scripted `sed`/`perl`** | **Rejected as primary.** | Cannot distinguish an import statement from the `pyarrow_filter.py` string literal or a docstring → guaranteed false positives across 4655 sites. Acceptable **only** for the 34 `ci.yml` bash lines and the 3 enumerated strings, where the surrounding context is known and hand-reviewed. |
| **IDE "rename module" refactor** | **Rejected.** | Not reproducible/auditable in CI, doesn't scale to 8 packages across a workspace, and chokes on the `src/` layout mid-migration. |

**Net tool decision:** ast-grep rule file for imports (idempotent, string-safe) + enumerated hand-edits for the 3 strings and the 34 `ci.yml` lines + `ruff --fix` (isort) as a formatting post-pass. Keep libcst in reserve for the symbol-aware ADR-3 moves if we choose to automate them.

---

## 4. Ordering relative to package extraction

The codemod is **not** a single big-bang run. It is run **incrementally, per extraction PR**, so the tree is green at every merge (ADR-7 phasing; FEATURES SCD-11…16). The governing rule:

> **A domain's references are rewritten in the same PR that physically moves that domain** (or immediately after, gated by CI). Never rewrite `pirn.domains.X` → `pirn_X` before `pirn_X` exists as an installed workspace member — that would red the tree.

Sequence, aligned to FEATURES topological order:

1. **Phase 1 (SCD-05/06) — connectors fold.** Apply **rule 0 only** (`pirn.domains.connectors` → `pirn.connectors`) across the whole repo *in the connectors-fold PR*. This is the 1255-hit case; landing it first removes the largest and most error-prone mapping while connectors physically lands in core. Verify C2 (core imports no domain) after.
2. **Phase 2 (SCD-08/09) — break edges.** The `EmbeddingProvider`/`LLMProvider` relocations are done **by hand in these PRs** (they are symbol-level moves, ~6 + ~2 files), re-pointing imports to `pirn.core.providers`. Excluded from the bulk codemod (§2 note) so the codemod stays a pure prefix rewrite.
3. **Phase 3 (SCD-11…16) — per-domain extraction.** For each domain in topological order (`signal` → `oilgas` → `data` → `ml` → `agents` → `health`): move the tree to `packages/pirn-<x>/src/pirn_<x>/`, then run the codemod **scoped to that domain's rule** across `pirn/`(remaining), `tests/`, `examples/`, `docs/`. After the PR merges, `grep -rn "pirn.domains.<that-domain>"` returns **only** the intentional compat shim.
   - **`ml` after `data`:** because `ml`'s `dataset_loader` imports `DataBatch` from data, the `ml→data` rule (rule 2, retained) only resolves once `pirn_data` exists — hence `data` extracts first.
4. **Phase 4 (SCD-17/18/21/22) — sweep + compat + adjacent fixes.** Run the **full** codemod once more over the whole repo as a catch-all (idempotent — a no-op if phases 1–3 were complete), land the `pirn.domains.*` compat shim (ADR-5, see §5), fix the 3 string literals (§3), rewrite `test_domains_extras.py` (§6), and update `mkdocstrings.paths` and `ci.yml` smoke lines (§6).

**Why incremental, not big-bang:** a single repo-wide rewrite would require *all* domains to be extracted simultaneously (one enormous unreviewable PR), and would red the tree between "move files" and "rewrite imports." Per-domain keeps each PR small, reviewable, and revertible (ADR-7 "each phase independently mergeable, leaves main green, reversible").

---

## 5. Backward-compat shim (legacy `pirn.domains.<x>` re-export) and lifecycle

This is the **consumer-facing** counterpart to the internal codemod. Internal code is migrated off `pirn.domains` entirely (§4); the shim exists for **external** consumers and for one deprecation cycle only. The mechanism is settled in ADR-5 (Option B→A); this section specifies its mechanics and lifecycle as they bear on the rewrite.

### Mechanism (lazy `__getattr__`, deferred import — no hard dep on domains)

`pirn-core` ships `pirn/domains/__init__.py` (the **only** surviving `pirn/domains` artifact):

```python
# packages/pirn-core/src/pirn/domains/__init__.py
_MAP = {"signal": "pirn_signal", "data": "pirn_data", "ml": "pirn_ml",
        "agents": "pirn_agents", "health": "pirn_health", "oilgas": "pirn_oilgas"}
# NOTE: "connectors" is intentionally absent — it folded into core as `pirn.connectors`.

def __getattr__(name):                 # PEP 562 module-level __getattr__
    if name in _MAP:
        import importlib, warnings
        warnings.warn(
            f"`pirn.domains.{name}` is deprecated and will be removed in pirn 1.0; "
            f"import `{_MAP[name]}` instead.",
            DeprecationWarning, stacklevel=2,
        )
        return importlib.import_module(_MAP[name])
    raise AttributeError(f"module 'pirn.domains' has no attribute {name!r}")
```

**Properties that matter for the rewrite:**
- **Deferred import** ⇒ `pirn-core` declares **no** hard dependency on any domain (C2 holds; verified by the dependency-tree check). If `pirn_<x>` isn't installed, `import pirn.domains.x` raises `ImportError` (from `importlib`) whose chained message names `pip install pirn-<x>`.
- **`connectors` is deliberately *not* in `_MAP`.** `pirn.domains.connectors` was the 1255-hit internal case rewritten to `pirn.connectors` in Phase 1; external consumers who used it get `AttributeError` pointing at the new `pirn.connectors` path. (A one-line connectors entry can be added to `_MAP` that re-exports `pirn.connectors` with a warning, **if** external telemetry shows it's needed — flagged as a judgment call for SCD-18.)
- **Covers only the `from pirn.domains.<x> import name` attribute form for the domain root.** Deep submodule imports (`from pirn.domains.data.sources.x import Y`) are **not** resurrected by `__getattr__` — PEP 562 only intercepts attribute access on the `pirn.domains` package object, not arbitrary deep submodule import machinery. **This is the shim's sharpest edge:** it soft-lands `import pirn.domains.data` / `from pirn.domains import data`, but **not** `from pirn.domains.data.sources.foo import Bar`. Consumers doing deep imports must run the codemod (SCD-23). Document this limit explicitly.

### Lifecycle

| Stage | Version | State |
|-------|---------|-------|
| Land shim | first workspace minor (e.g. `0.4.0`) | `pirn.domains.<x>` works, emits `DeprecationWarning`; internal tree uses `pirn_<x>` exclusively. |
| Deprecation window | through `0.x` | One minor release of soft-landing (ADR-5). CI asserts the warning fires (a test imports `pirn.domains.data` under `pytest.warns(DeprecationWarning)`). |
| Remove shim (Option A) | `1.0` (major, lockstep bump — ADR-6) | Delete `pirn/domains/`. `import pirn.domains.x` → `ModuleNotFoundError`. Codemod + migration guide (SCD-23) is the documented fix. |

The shim's warning text and `_MAP` are the **canonical mapping** consumers see; keep it in sync with §2 (sans connectors).

---

## 6. Adjacent fixes (not import statements, but must change with the rewrite)

These are enumerated so none is missed; each is small and hand-applied in the phase noted.

| Item | File(s) | Change | Phase |
|------|---------|--------|-------|
| `ExtrasLoader` message + docstring | `extras_loader.py` (moves with domains; one copy per domain package, or a shared core copy) | `f"pirn.domains.{extra} requires…"` → `f"pirn_{extra} requires…"`; install hint `pip install 'pirn[{extra}]'` → `pip install 'pirn-{extra}[{extra}]'` (confirm extra-naming with devops in SCD-06/13). Docstring line 3 `pirn.domains.<name>` → `pirn_<name>`. | per-domain (Phase 3) |
| 2 filter string literals | `data/frames/pyarrow/pyarrow_filter.py:92`, `polars/polars_filter.py:75` | `"pirn.domains.data.transforms.filter.Filter"` → `"pirn_data.transforms.filter.Filter"` | data extraction (SCD-13) |
| `test_domains_extras.py` sys.modules | `tests/unit/test_domains_extras.py` (8 `pop("pirn.domains.X")` lines + `from pirn.domains import extras_loader`) | `sys.modules.pop("pirn.domains.<x>")` → `pop("pirn_<x>")`; `pirn.domains.connectors` → `pirn.connectors`; the bare `from pirn.domains import extras_loader` → import from wherever ExtrasLoader lands. Rewrite by hand (test asserts import-time side effects). | Phase 4 (SCD-19) |
| CI smoke imports | `.github/workflows/ci.yml` (34 lines) | bash `import pirn.domains.data` → `import pirn_data`; `import pirn.domains.connectors` → `import pirn.connectors`. `sed` is acceptable here (known, reviewed context). | Phase 4/5 (SCD-22/24) |
| `mkdocstrings.paths` | `mkdocs.yml:17` `paths: [pirn]` | → `paths: [pirn, pirn_signal, pirn_data, pirn_ml, pirn_agents, pirn_health, pirn_oilgas]` (connectors documented under `pirn`). | Phase 4 (SCD-22) |
| Docs prose/code-blocks | `docs/**` (~115 hits) | Codemod handles code-blocks if ast-grep is pointed at fenced Python; prose mentions of `pirn.domains.<x>` updated by document-agent. | Phase 4 (SCD-22) |

**Not touched by the codemod:** tapestry `*.yaml` `callable:` references (they use bare knot names / `examples.*` paths, resolved by the registry — ADR-4 R1, not by `pirn.domains` dotted path). Registry behaviour is out of scope for the *import* rewrite.

---

## 7. Verification

Run after **each** incremental codemod pass (per §4) and as a final gate.

1. **Residual-reference grep (per phase).** After extracting domain `X`: `grep -rn "pirn\.domains\.<X>" pirn/ tests/ examples/ docs/` returns **only** the compat shim file (or nothing, pre-shim). For connectors: zero `pirn.domains.connectors` anywhere.
2. **Import smoke.** In a clean env with the relevant package installed: `python -c "import pirn_<x>"` for each extracted domain; `python -c "import pirn; import pirn.connectors"` for core. Asserts the rewrite produced importable modules (no dangling `pirn.domains.X` submodule import).
3. **Idempotency.** Re-run the codemod; `git diff` must be empty. Proves the rule set is a fixpoint and safe to re-run in the Phase-4 catch-all.
4. **Full test suite.** `uv run pytest` green against installed split packages (no behaviour change — the split is structural; ADR-5/PRD success metric "no behaviour change"). The `src/` layout guarantees tests run against the *installed* package, surfacing any missed rewrite as an `ImportError`.
5. **Type check.** `pyright` (or `mypy`) over the workspace: a missed/incorrect rewrite shows as `reportMissingImports`/unresolved-import. Run per-package per the shared base config (SCD-03).
6. **Registry parity.** A cross-domain tapestry (data + ml + agents) resolves all knots by bare name after importing those packages (ADR-4 R1 metric) — confirms the rewrite didn't break the `fill_registry` scan path (e.g. by leaving a module unimportable, which `fill_registry` would silently skip).
7. **Deprecation-warning test.** `pytest.warns(DeprecationWarning)` on `import pirn.domains.data` (shim landed) — confirms the soft-landing path.
8. **String-leak grep (final).** Repo-wide `grep -rn "pirn\.domains"` returns only: the shim module, intentional historical references in `planning/`/changelog, and (until 1.0) the deprecation test. Any other hit is a missed adjacent fix from §6.

CI wiring: checks 1, 3, 5, 6 become required gates (1 and 3 are cheap greps/diffs; 5/6 already exist as workspace checks per FEATURES SCD-07/10/24).

---

## 8. Summary

The rewrite is large (~4655 sites) but **mechanically uniform**: every reference is the `from pirn.domains.X import …` form, there are **no** aliased or bare `import pirn.domains.X` forms, **no** relative imports inside domains, and **no** dynamic `import_module("pirn.domains…")` dispatch. That uniformity makes an **ast-grep rule-file** (string-safe, idempotent) the right bulk tool, with libcst held in reserve for the symbol-aware ADR-3 moves and `ruff --fix` as an import-sort post-pass. The codemod runs **incrementally, inside each extraction PR** (connectors-fold first, then topological domain order), so `main` stays green; a final idempotent catch-all + the `pirn.domains.*` lazy-`__getattr__` compat shim (deprecate at first minor, remove at 1.0) cover external consumers. Verification is grep-residual + idempotency-diff + full pytest/pyright + registry-parity.

### Riskiest rewrite cases

1. **`connectors` (1255 hits) maps differently** — `pirn.domains.connectors` → **`pirn.connectors`** (folded into core), *not* `pirn_connectors`. A naïve uniform `pirn.domains.<x>` → `pirn_<x>` rule corrupts the single most common case. Mitigation: dedicated, **first-priority** rule 0; exclude connectors from `_MAP` in the shim; explicit residual grep for `pirn.domains.connectors == 0`.
2. **Symbol-aware break edges (`EmbeddingProvider`, `LLMProvider`)** — same `pirn.domains.ml.*`/`pirn.domains.agents.*` prefix, but these two symbols relocate to `pirn.core.providers`, not `pirn_ml`/`pirn_agents`. A prefix-only codemod sends them to the wrong package. Mitigation: do these moves **by hand in SCD-08/09**, exclude from the bulk prefix rewrite.
3. **Shim does not cover deep submodule imports** — PEP 562 `__getattr__` resurrects `import pirn.domains.data` but **not** `from pirn.domains.data.sources.x import Y`. External consumers doing deep imports get `ModuleNotFoundError` even during the deprecation window. Mitigation: document the limit; the codemod (SCD-23) is the only fix for deep imports.
4. **3 string literals + 34 `ci.yml` lines are invisible to an AST import-rewriter** — `extras_loader.py` f-string, two `*_filter.py` error strings, and the CI bash smoke lines are not import nodes. Mitigation: enumerate and hand-fix (§6); final string-leak grep (check 8) catches misses.
5. **`ml→data` retained vs. `agents→ml`/`health→agents` broken** — easy to over-apply the "break the edge" instinct and wrongly hoist `DataBatch` to core. `ml→data` is a **declared dependency** (rule 2, normal `pirn_data` mapping), *not* a relocation. Mitigation: the override table (§2) lists `DataBatch` explicitly as **no override**; topological-order check (C3) asserts the `ml→data` edge survives.
