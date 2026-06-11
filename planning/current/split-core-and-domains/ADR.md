# ADR: Split Core and Domains — Architectural Decisions

**Status:** Accepted (planning)
**Date:** 2026-06-09
**Tracking Issue:** [#51](https://github.com/snoodleboot-io/pirn/issues/51)
**Companion docs:** `PRD.md` (this directory), `FEATURES.md` (this directory)
**Scope:** Planning only. No source code is moved, renamed, or refactored by this ADR. It records the target architecture and the rationale that execution issues (from `FEATURES.md`) will implement.

---

## Context

`pirn` ships today as a **single Hatch wheel** (`pirn` 0.3.0, build-backend `hatchling`, `packages=["pirn"]`). One distribution bundles core infrastructure and all seven domain libraries under `pirn/domains/`.

**Verified facts (ground truth for this ADR):**

- **Core (non-domain) modules** — `core`, `engine`, `nodes`, `backends`, `emitters`, `managers`, `streaming`, `triggers`, `viz`, `yaml_loader`, `exceptions`, plus `tapestry.py` and `replay.py` — import **zero** domains. Layering is clean by convention, not by package boundary.
- **`pirn/__init__.py`** calls `sweet_tea.Registry.fill_registry()` at import time (under a `SweetTeaWarning` suppression), then re-exports the public API (`Assembler`, `Disassembler`, `Knot`, `KnotConfig`, `Tapestry`, `knot`, `Parameter`, `RunRequest`, `RunResult`, `ErrorPolicy`, and node bases `Source`, `Sink`, `SubTapestry`, `LoopSubTapestry`).
- **`fill_registry()` semantics (verified by reading `sweet_tea.registry`):** with no `path`, it resolves the **caller's module directory** via `inspect.stack()[1][0]`; it recursively walks the package with `pkgutil.iter_modules`, `importlib.import_module`s each module, and registers every class **defined in that module** (`obj.__module__ == name_of_package`) under `Registry.register(key=class_name.lower(), library=library)`. **`library` defaults to the scanned package's basename**, but is an **explicit keyword argument**. Modules that fail to import (missing optional deps) are skipped with a warning, not raised.
- **7 domains** under `pirn/domains/`: signal (133 files / ~111 knots, standalone), data (250 / ~175), connectors (268 / ~10, the hub), oilgas (125 / ~95), health (143 / ~115), agents (172 / ~136), ml (153 / ~116).
- **Cross-domain import DAG (acyclic):** `data→connectors`, `ml→connectors`, `ml→data`, `agents→connectors`, `agents→ml`, `health→connectors`, `health→agents`, `oilgas→connectors`. `signal` is standalone.
- **Residual domain→domain edges** (do **not** resolve by folding connectors): `ml→data` (~5: `DataBatch`, `LakehouseTable`, `FileSource`, `SqlSource` in `dataset_loader`), `agents→ml` (~5: `EmbeddingProvider` in RAG document_processing), `health→agents` (~1: `LLMProvider` in `clinical_nlp_extractor`).
- **Key symbol locations (verified):** `EmbeddingProvider` in `pirn/domains/ml/embedding_provider.py` (subclasses `PirnOpaqueValue`), `LLMProvider` in `pirn/domains/agents/llm_provider.py`, `DataBatch` in `pirn/domains/data/data_batch.py`. Connector interfaces (`database_connection_pool.py`, `object_store.py`, `message_broker.py`, `file_format.py`, `connection_config.py`, `api_client.py`, `dsn_scrubber.py`) live at the top of `pirn/domains/connectors/`.
- **Optional deps** are already partitioned per-domain in `pyproject.toml` extras; `numpy` is registered into the serializer **conditionally** (only if importable).

### Decision drivers

1. **Install isolation.** A consumer who wants only `pirn_signal` should pull `pirn-core` + scipy/pywavelets/librosa and nothing from data/ml/health/oilgas.
2. **Enforced layering.** The clean core→(no domain) and acyclic domain DAG should be guaranteed by package boundaries and an automated import-graph check, not by convention.
3. **Independent versioning/release cadence.** Domains mature at very different rates; a `data` bugfix should not force a whole-monolith re-release.
4. **Preserve the core public API.** `from pirn import Knot, Tapestry, ...` must keep working unchanged.
5. **Bounded blast radius.** The `import pirn.domains.<x>` break is accepted but must have a documented, tooled migration path and a soft-landing window.

The hard tension: **install isolation and independent versioning pull toward many packages**, while **the runtime knot Registry and YAML bare-name resolution assume one process-wide `library="pirn"` namespace populated at `import pirn` time**. The whole ADR is an exercise in getting the first without breaking the second.

---

## ADR-1: uv Monorepo Workspace, Eight Packages

### Decision

Restructure the repo into a **uv workspace**: one git repo, eight independently-installable packages under `packages/`. Core installs as `pirn-core` but **imports as `pirn`** (preserving the public API); each domain installs as `pirn-<domain>` and imports as `pirn_<domain>`.

#### On-disk layout

```
pirn/                                  # repo root (workspace root)
├── pyproject.toml                     # [tool.uv.workspace] root; NOT itself a published wheel
├── uv.lock                            # single lockfile for the whole workspace
├── packages/
│   ├── pirn-core/
│   │   ├── pyproject.toml
│   │   └── src/pirn/                  # core + engine + nodes + backends + emitters +
│   │       ├── __init__.py            #   managers + streaming + triggers + viz +
│   │       ├── core/ engine/ nodes/   #   yaml_loader + exceptions + tapestry + replay
│   │       ├── backends/ emitters/    #   + connectors/  (folded in — see ADR-2)
│   │       ├── managers/ streaming/
│   │       ├── triggers/ viz/
│   │       ├── yaml_loader/ exceptions/
│   │       ├── connectors/            # was pirn/domains/connectors
│   │       ├── tapestry.py replay.py
│   ├── pirn-signal/
│   │   ├── pyproject.toml
│   │   └── src/pirn_signal/           # was pirn/domains/signal
│   ├── pirn-data/      └── src/pirn_data/
│   ├── pirn-ml/        └── src/pirn_ml/
│   ├── pirn-agents/    └── src/pirn_agents/
│   ├── pirn-health/    └── src/pirn_health/
│   └── pirn-oilgas/    └── src/pirn_oilgas/
├── tests/                             # may stay centralized or move per-package (FEATURES)
├── examples/  docs/  mkdocs.yml
```

`src/` layout is chosen deliberately: it forces tests to run against the **installed** package, which is exactly the property we need to assert install isolation (you cannot accidentally import a domain that isn't a declared dependency).

#### Root workspace `pyproject.toml` (skeleton)

```toml
[tool.uv.workspace]
members = ["packages/*"]

# Path wiring so intra-workspace deps resolve to local source, not PyPI, during dev/CI.
[tool.uv.sources]
pirn-core   = { workspace = true }
pirn-signal = { workspace = true }
pirn-data   = { workspace = true }
pirn-ml     = { workspace = true }
pirn-agents = { workspace = true }
pirn-health = { workspace = true }
pirn-oilgas = { workspace = true }

# Dev/CI convenience: a virtual "everything" target (see ADR-6 for the published meta-extra).
[dependency-groups]
all = ["pirn-core", "pirn-signal", "pirn-data", "pirn-ml",
       "pirn-agents", "pirn-health", "pirn-oilgas"]
```

#### Per-package `pyproject.toml` (skeletons)

`pirn-core`:

```toml
[project]
name = "pirn-core"
version = "0.4.0"                      # see ADR-6 versioning
requires-python = ">=3.11"
dependencies = ["sweet_tea>=0.2.46"]

[project.optional-dependencies]
# ALL connector/backend extras fold in here (ADR-2):
sqlite = ["aiosqlite"]; postgres = ["asyncpg"]; duckdb = ["duckdb"]
s3 = ["aioboto3"]; gcs = [...]; kafka = [...]; valkey = [...]
zstd = ["zstandard"]; snappy = ["python-snappy"]; lz4 = ["lz4"]
all-db = [...]; all-storage = [...]; all-stream = [...]   # aggregates

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pirn"]               # imports as `pirn`
```

`pirn-signal` (template for every domain; deps/extras vary per the mapping below):

```toml
[project]
name = "pirn-signal"
version = "0.4.0"
requires-python = ">=3.11"
dependencies = ["pirn-core"]          # lower-bound pinned per ADR-6

[project.optional-dependencies]
signal = ["scipy", "pywavelets", "librosa"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pirn_signal"]
```

#### Package dependency graph (after ADR-3 edge resolution)

```
                         ┌─────────────┐
                         │  pirn-core  │  (sweet_tea; folds in connectors)
                         └─────────────┘
        ┌──────────┬──────────┬─────────┴───┬──────────┬──────────┐
        │          │          │             │          │          │
  pirn-signal  pirn-oilgas pirn-data    pirn-health pirn-agents pirn-ml
   (standalone) (→core)    (→core)       (→core)    (→core)   (→core, →data)
                              ▲                                    │
                              └────────────────────────────────────┘
                                        pirn-ml → pirn-data  (retained edge)
```

After ADR-3, the **only** retained domain→domain edge is `pirn-ml → pirn-data`. Every other domain depends on `pirn-core` alone. The graph is a tree rooted at `pirn-core` plus that single extra edge — trivially acyclic.

### Data-model lens (package/dependency graph as an entity model)

Treating packages as entities and dependencies as a one-directional relation:

```
PACKAGE {
  string  dist_name   PK   # pirn-core, pirn-signal, ...
  string  import_name       # pirn, pirn_signal, ...
  string  version           # ADR-6
  bool    is_core
}
DEPENDS_ON {
  string  from_pkg    FK
  string  to_pkg      FK
  string  kind             # "hard" (install dep) | "extra" (optional)
}

PACKAGE ||--o{ DEPENDS_ON : "declares"
PACKAGE ||--o{ DEPENDS_ON : "depended-on-by"
```

**Integrity constraints (must be CI-enforced — the equivalent of FK + check constraints):**

- **C1 (no self/cycle):** the transitive closure of `DEPENDS_ON(kind="hard")` is a DAG. *Index/check:* topological sort in CI; fail on back-edge.
- **C2 (core is a sink):** no row where `from_pkg = 'pirn-core'` and `to_pkg LIKE 'pirn-%'` (other than `sweet_tea`). Core imports zero `pirn_*` domains. *Check:* import-graph scan of `src/pirn/` for `pirn_<domain>` imports.
- **C3 (single edge invariant):** exactly one domain→domain hard edge after ADR-3 (`pirn-ml → pirn-data`). New domain→domain edges require an ADR amendment.
- **C4 (version floor):** every `DEPENDS_ON` to `pirn-core` pins `>=` the core version that introduced the symbols it uses (ADR-6 compatibility floor).

This is the data-model that the success-metric "acyclic package graph" check operationalizes.

### Alternatives rejected

| Alternative | Reason rejected |
|-------------|-----------------|
| **Monorepo with a single package** (status quo) | Fails all three primary drivers: no install isolation, no per-domain versioning, layering only by convention. This is exactly what ADR-2 of the *previous* initiative chose, and the new drivers (isolation, independent release) explicitly supersede it. |
| **PEP 420 implicit namespace packages** (`pirn.signal`, `pirn.data` as separate distributions all under the `pirn` namespace) | Tempting for API continuity, but: (a) every distribution must omit `pirn/__init__.py`, which is where `fill_registry()` and the core public-API re-exports live — we would have to relocate the core API anyway; (b) namespace packages are fragile under editable installs and mixed regular/namespace layouts, and a single stray `__init__.py` silently shadows the namespace; (c) it does not actually buy back the `pirn.domains.<x>` call sites (they would become `pirn.<x>`, still a break). Distinct top-level names are simpler to reason about and to enforce. **Rejected.** |
| **Polyrepo (one git repo per package)** | Maximizes release independence but cross-domain pipeline composition, coordinated refactors (e.g. an `Assembler` contract change), and a single `uv.lock` become cross-repo coordination problems. The workspace gives us most of the isolation with one-repo ergonomics. **Rejected.** |
| **Multi-package but flat (no `packages/` dir, packages at root)** | Workable, but clutters the root and complicates `members` globbing and tooling discovery. `packages/*` is the idiomatic uv-workspace layout. **Rejected (cosmetic).** |

---

## ADR-2: Fold `connectors` into `pirn-core`

### Decision

`pirn/domains/connectors` is relocated **into the core package** at `packages/pirn-core/src/pirn/connectors/` (a top-level subpackage of core, **not** under a `domains/` directory). After the fold, every `→connectors` edge (data, ml, agents, health, oilgas) becomes a `→core` edge.

#### What lands where

- **Interfaces** (`DatabaseConnectionPool`, `ObjectStore`, `MessageBroker`, `APIClient`, `FileFormat`, `ConnectionConfig`, `DsnScrubber`, `FileFormatRegistry`) become part of `pirn-core`'s **public surface**, importable as `pirn.connectors.<x>` and re-exported from a stable `pirn.connectors` namespace.
- **Backend implementations** (databases, object_storage, messaging, saas, bi_catalog, graph, timeseries, streaming, document, observability) and the **file-format codec ecosystem** (~90 files) move with them but stay behind **optional extras** declared in `pirn-core`'s `pyproject.toml`.
- `PirnOpaqueValue`, `DataTransport`, `SerializerRegistry` are already in `pirn.core.*`; connector code keeps importing them from those stable paths. **Open question #5 resolved:** connector public surface is namespaced under `pirn.connectors.*`; we do **not** flatten interfaces into unrelated core modules.

#### Third-party deps this adds to core

Core's **hard** dependency stays exactly `sweet_tea>=0.2.46`. Everything connectors pulls (asyncpg, aioboto3, aiomysql, snowflake-connector, kafka clients, zstandard/snappy/lz4, pyarrow for some formats, etc.) is added **only as optional extras**, mirroring today's partitioning. **Contract boundary (enforced):** no module imported at `pirn` import time may top-level-import a backend dependency. Concrete backends import their heavy deps **lazily** (inside methods / `try-except` / `ExtrasLoader.require()`), exactly as they do today. The conditional `numpy` serializer registration pattern is the template.

### Rationale

connectors is an **infrastructure hub, not a domain**: it defines 268 files but only ~10 knots, and those are factory knots that wire user-supplied pools/stores into a tapestry. Four of seven domains import it for pure-Python interface types. Making it a peer domain package would force a `pirn-connectors` dependency into nearly every domain and re-introduce a hub-domain the design explicitly wants to eliminate. Folding it into core makes "needs a connection/format" mean "needs core," which is already true transitively.

### Risk + mitigation

Promoting connectors enlarges core's **public contract** (a breaking-change surface). Mitigation: phase the fold (interfaces first, backends per category, codecs in batches — see ADR-7) and add a CI check (C2 above) that **no backend dependency is imported at core import time**, so a careless backend addition can't leak a transitive hard dep into core.

### Alternative rejected

| Alternative | Reason rejected |
|-------------|-----------------|
| **Keep `connectors` as its own package `pirn-connectors`** | Re-introduces a hub package that almost every domain must depend on, and forces a decision about whether it's "core infra" or "a domain" (the Discovery naming ambiguity). It also splits the interface types (`DatabaseConnectionPool` etc.) from core, so either core re-exports them (coupling) or domains depend on both core and connectors. Folding into core removes the ambiguity and the extra edge. **Rejected.** |

---

## ADR-3: Per-Edge Resolution of Residual Inter-Domain Dependencies

Folding connectors does **not** resolve the three domain→domain edges. Each is decided on its own merits: **break it** (relocate the crossed symbol to core / define an interface in core) vs **declare an explicit package dependency**. Guiding principle: **pure abstract interfaces with no domain logic belong in core; concrete domain data types stay in their domain and justify an explicit dependency.**

### Edge `agents → ml` — **BREAK** (move `EmbeddingProvider` to core)

- **Crossed symbol:** `EmbeddingProvider` (in `pirn/domains/ml/embedding_provider.py`), a pure abstract interface subclassing `PirnOpaqueValue`, intentionally unimplemented in ml.
- **Decision:** relocate `EmbeddingProvider` to `pirn.core` (e.g. `pirn/core/providers/embedding_provider.py`), re-export from `pirn.connectors`/core public surface. Both `agents` (RAG) and `ml` import it from core.
- **Rationale:** it is a contract, not a domain capability. An abstract provider interface is conceptually the same kind of thing as `Assembler`/`Disassembler`/`PirnOpaqueValue`, which already live in core. Moving it **eliminates the `pirn-agents → pirn-ml` edge entirely** — agents no longer needs ml installed.
- **Cost:** `ml`'s embedding implementations now subclass a core base (an import-path change, no behaviour change). ~5 agents files + the ml base move. Low.

### Edge `health → agents` — **BREAK** (move `LLMProvider` to core)

- **Crossed symbol:** `LLMProvider` (in `pirn/domains/agents/llm_provider.py`), a pure abstract async chat/stream interface; only `clinical_nlp_extractor` consumes it from health.
- **Decision:** relocate `LLMProvider` (and its tightly-coupled `Tool`/`FunctionTool` abstract bases if they travel with it) to `pirn.core.providers`. health and agents both import from core.
- **Rationale:** identical to the agents→ml case — a provider **interface** with no agent logic. Forcing `pirn-health` to depend on the entire `pirn-agents` package (136 knots) for one abstract base is the tail wagging the dog. Moving it **eliminates the `pirn-health → pirn-agents` edge**.
- **Cost:** 1 health file + the agents base move + agents' concrete LLM providers re-point their import. Low.

### Edge `ml → data` — **DECLARE explicit dependency** `pirn-ml → pirn-data`

- **Crossed symbols:** `DataBatch`, `LakehouseTable`, `FileSource`, `SqlSource` (in `dataset_loader`).
- **Decision:** keep these in `pirn-data` and **declare `pirn-ml`'s hard dependency on `pirn-data`.**
- **Rationale:** unlike the two provider interfaces, these are **concrete, behaviour-bearing data types** (`DataBatch` is the data domain's central tier-1 type; `LakehouseTable`/`FileSource`/`SqlSource` are real source/table abstractions with logic). Hoisting `DataBatch` into core would drag the data domain's conceptual center of gravity into core and blur the core/data boundary — and `data` already depends on core, so the type genuinely belongs in data. ML legitimately *is* a consumer of the data domain (dataset loading), so the dependency is semantically honest. `data` does **not** import `ml`, so the edge is one-directional and acyclic.
- **Cost:** `pirn-ml` lists `pirn-data` in `dependencies`. Installing `pirn-ml` transitively installs `pirn-data`. Accepted.

### Resulting graph

Every domain → core; **plus exactly one** domain→domain edge: `pirn-ml → pirn-data`. Acyclic (constraint C3). This matches the "flattened graph" the PRD describes as the preferred outcome.

| Edge | Decision | Mechanism | Eliminates edge? |
|------|----------|-----------|------------------|
| `agents → ml` | **Break** | Move `EmbeddingProvider` → `pirn.core.providers` | Yes |
| `health → agents` | **Break** | Move `LLMProvider` (+`Tool`) → `pirn.core.providers` | Yes |
| `ml → data` | **Declare dep** | `pirn-ml.dependencies += pirn-data` | No (kept, acyclic) |

---

## ADR-4: Registry / Import-Time Discovery Under Distinct Top-Level Packages

**This is the highest-risk decision.** It is grounded in the **verified** `sweet_tea` source (see Context).

### Decision — R1: per-package self-registration under the shared `library="pirn"`

Each domain package registers its own knots **into the same logical library** that core uses, by calling `fill_registry` from its own `__init__.py` with **explicit `module` and `library` arguments**:

```python
# packages/pirn-signal/src/pirn_signal/__init__.py
import warnings
from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SweetTeaWarning)
    # module=__name__ so the recursive scan walks pirn_signal/, and
    # library="pirn" so knots land in the SAME namespace YAML expects today.
    Registry.fill_registry(module=__name__, library="pirn")
```

`pirn-core`'s `pirn/__init__.py` keeps its existing call, but **must now scope its scan to core only** (it no longer contains `domains/`, so a bare `fill_registry()` will naturally scan only `packages/pirn-core/src/pirn/`, registering core + connector knots under `library="pirn"`). No domain knots are discovered by `import pirn` — they self-register when their package is imported.

#### Why this works (verified, not assumed)

- `fill_registry(path=None)` uses **the caller's module directory**; passing `module=__name__` makes the recursive walk and `importlib.import_module` use the correct `pirn_<domain>.*` dotted names. Without `module`, the recursion would re-derive the module name from the path **basename**, which is fragile under `src/` layouts — so we pass it explicitly.
- `library` is an explicit keyword; passing `library="pirn"` registers under the **same library** as core. `Registry.register(key=class_name.lower(), …)` stores an `Entry` keyed by the **lowercased class name**. Two classes that share a lowercased name are stored as **two distinct entries** (`Entry` is a Pydantic model comparing all fields incl. `class_def`), and a bare-name lookup — `AbstractInverterFactory[Knot].create(ref)` with no `library`/`label` — **raises `SweetTeaError`** when >1 entry matches (`inverter_factory.py:126`). ⚠️ **Knot class names are NOT globally unique today** — 5 real collisions exist (`bandpassfilter`, `notchfilter`, `databaseconnectionpoolknot`, `messagebrokerknot`, `freshnesscheck`); see "Knot key collisions (B1)" below. R1 inherits this latent monolith bug, and the connectors fold turns two of them into cross-package (core↔`pirn-data`) collisions — so R1 is viable **only after** SCD-01 resolves the 5 collisions.
- Missing optional deps are skipped with a `SweetTeaWarning`, so a domain with un-installed extras still imports and registers the knots whose modules *do* import — identical to today's behaviour.

#### The contract this establishes

> **Installing/importing a `pirn-<domain>` package self-registers its knots under `library="pirn"`.** Bare-name YAML (`callable: object_store_read_source`) continues to resolve **once the owning domain package has been imported** (directly, or transitively, before the YAML loads).

This is the one behavioural rule consumers must learn. We mitigate it three ways:

1. **Document it** prominently (the "import the domain to register its knots" rule).
2. **Provide a startup helper** in core, e.g. `pirn.discover_installed_domains()`, that introspects installed `pirn_*` distributions (via `importlib.metadata`) and imports them, restoring the "import `pirn`, get everything" ergonomics for users who opt in. This is a **convenience**, not the discovery mechanism — discovery stays Registry-reflection-based per the PRD non-goal.
3. **Improve the loader error.** When `AbstractInverterFactory[Knot].create(ref)` misses, the `yaml_loader` should raise a message naming the likely owning package ("knot `X` not found; did you `pip install`/import its domain package?").

#### Knot key collisions (B1) — required resolution before R1

R1 keeps the shared `library="pirn"` namespace, so every knot key must be globally unique. Five keys are **not** unique today (each maps to 2 distinct, registered `Knot` subclasses). Per-pair investigation (diffed implementations) dictates the resolution; the strategy is **consolidate the one true duplicate, rename the four genuine variants** — preserving R1 bare-name resolution:

| Key | Entry A | Entry B | Same impl? | Resolution |
|-----|---------|---------|-----------|------------|
| `databaseconnectionpoolknot` | `connectors` (→ core) | `data/specializations/incremental` | **Yes** — both are thin `return pool` vending knots; B only adds docstrings | **Consolidate**: delete B, re-export core's from `pirn-data` if a `pirn_data` import path is needed |
| `messagebrokerknot` | `connectors` (→ core) | `data/.../scd/cdc` | **No** — A returns `MessageBroker`; B wraps in data-specific `MessageBrokerConnection` | **Rename B** → `CdcMessageBrokerKnot` (stays in `pirn-data`); A stays `MessageBrokerKnot` in core |
| `freshnesscheck` | `data/quality` (in-memory `DataBatch`) | `data/specializations/quality` (SQL `MAX(ts)` SLA) | **No** — different inputs/semantics; both in `data` | **Rename B** → `TableFreshnessCheck` (SQL SLA variant); both stay in `pirn-data` |
| `bandpassfilter` | `signal` (causal `sosfilt`) | `health/eeg_meg` (zero-phase `sosfiltfilt`) | **No** — EEG zero-phase variant; health does not import signal | **Rename B** → `EegBandpassFilter` (stays in `pirn-health`) |
| `notchfilter` | `signal` (configurable Q, `sosfilt`) | `health/eeg_meg` (zero-phase, Q=30) | **No** — EEG zero-phase variant | **Rename B** → `EegNotchFilter` (stays in `pirn-health`) |

Only `DatabaseConnectionPoolKnot` is a true duplicate to merge; the other four are genuinely distinct implementations that must keep distinct registry keys. Names above are proposals — executors may refine, but uniqueness under `library="pirn"` is the hard requirement. R2 (per-package `library`) remains rejected as the *primary* strategy, but renaming is cheap because it rides the mass rename already in scope.

#### Decision note — R1 confirmed, B1 amended (SCD-01 / #52 execution outcome, 2026-06-11)

**R1 is CONFIRMED.** Executing SCD-01 against the live registry validated the mechanism end-to-end: `Registry.fill_registry(module=…, library="pirn")` self-registers a separate top-level package's knots under the shared `"pirn"` library, and `BaseFactory.create()` resolves them by bare (lowercased class-name) key, raising `SweetTeaError` only when >1 distinct class matches. The shared-`library` + rename strategy (not R2) holds.

**B1 is AMENDED — the collision count was understated. The real number is 15, not 5.** A ground-truth audit (build the registry as `import pirn` does, then group `Entry` by `(key, library)`) found **15** duplicate keys, every one of which makes bare-name `create()` raise today. The original B1 list (5) was both incomplete and partly mis-specified:

- **Mis-specified:** `bandpassfilter`'s signal sibling is `signal/filters/band_pass_filter.py::BandPassFilter` (not `bandpass_filter_bank.py::BandpassFilterBank`, which is a distinct key); `freshnesscheck` is **intra-`data`** (two `data/` knots), not cross-domain.
- **Missing (10):** `signalframe`, `signalpayload` (health vs signal — **cross-package**); `datasetmanifest`, `datasetpayload`, `datasplitpayload`, `evalreportpayload`, `trainedmodelpayload`, `imageembeddingextractor` (intra-`ml`); `opentelemetryemitter` (core: `connectors` vs `emitters`); `parameterspec` (core: `core` vs `yaml_loader`).

**Resolution executed (all 15, behavior-preserving):**

| Kind | Count | Items → action |
|------|------:|----------------|
| Delete deprecated duplicate stub modules (0 importers) | 5 | `ml/types/{ml_dataset, ml_dataset_payload, data_split, eval_report, trained_model}.py` → `git rm` (canonical `dataset_manifest`/`*_payload` modules retained) |
| Delete orphaned duplicate (0 importers) | 1 | `data/specializations/incremental/database_connection_pool_knot.py` → `git rm`; test repointed to the `connectors` class |
| Rename genuine variant (class + `git mv` file + refs) | 9 | health `BandpassFilter`→`EegBandpassFilter`, `NotchFilter`→`EegNotchFilter`, `SignalFrame`→`HealthSignalFrame`, `SignalPayload`→`HealthSignalPayload`; data `MessageBrokerKnot`→`CdcMessageBrokerKnot`, specialization `FreshnessCheck`→`DatabaseTableFreshnessCheck`; core `OpenTelemetryEmitter`(connectors)→`OpenTelemetrySpanEmitter`, `ParameterSpec`(yaml_loader)→`YamlParameterSpec`; ml specialization `ImageEmbeddingExtractor`→`FeatureEngineeringImageEmbeddingExtractor` |

**Architectural correction vs the B1 proposal:** `signalframe`/`signalpayload` are resolved by **renaming the health side** (`HealthSignalFrame`/`HealthSignalPayload`), *not* by consolidating health→signal. Consolidation would introduce a `pirn-health → pirn-signal` package edge, which the ADR-1/ADR-3 target graph forbids (health depends on core only). Health is confirmed self-contained (imports nothing from signal), so the rename keeps the package graph intact.

**Verification:** a new acceptance test `tests/unit/test_registry_uniqueness.py` asserts zero `(key, library)` collisions across the whole registered set — RED at 15 before, GREEN after. `ruff check pirn/` + `ruff format --check pirn/` clean; `pyright` 0 errors; the affected-domain unit tests pass (1067 passed, only a pre-existing nibabel `motion_corrector` env failure remains), including `--real` Postgres/Kafka for the consolidated pool and renamed CDC broker.

### Alternatives rejected

| Alternative | Reason rejected |
|-------------|-----------------|
| **R2 — distinct library per package** (`library="pirn_data"`, ...) | Avoids name collisions but **breaks every existing bare-name YAML**, which is the single most-used resolution path. The 5 real collisions (B1) are instead resolved by consolidation+rename (see "Knot key collisions"), which keeps the shared `library="pirn"` namespace intact. **Rejected as primary.** |
| **R3 — fully-qualified dotted paths in YAML** (`callable: pirn_data.sources.object_store_read_source`) | Explicit and unambiguous, but imposes a large, mechanical YAML migration on every consumer and abandons the registry's main ergonomic benefit. Reserve dotted-path resolution as the existing fallback (step 3 in the loader), not the primary path. **Rejected as primary.** |
| **Entry-point-based discovery** (`[project.entry-points."pirn.knots"]`) | Cleanest "install = discoverable" story and would let `import pirn` auto-load installed domains. But: (a) the PRD declares entry points a **non-goal** as the primary mechanism; (b) `sweet_tea`'s registry is reflection-based and has no entry-point hook today, so this is a `sweet_tea` feature request, not a `pirn` change. **Deferred** — revisit only if R1's "import to register" rule proves too sharp; the `discover_installed_domains()` helper can be re-implemented over entry points later without changing the contract. |

### Adjacent required fixes (regardless of option)

- `pirn/domains/extras_loader.py` (moves with the domains): error text `pirn.domains.<x> requires...` → `pirn_<x> requires...`.
- Stale docstrings/error strings referencing `pirn.domains.*`.
- `test_domains_extras.py` `sys.modules` manipulation: rewrite to pop `pirn_<x>` keys.

---

## ADR-5: Public-API / Import-Compatibility Strategy

### Decision

**Core public API: hard-preserved.** Because `pirn-core` keeps the `pirn` import name, `from pirn import Knot, KnotConfig, Tapestry, knot, Parameter, RunRequest, RunResult, ErrorPolicy, Assembler, Disassembler, Source, Sink, SubTapestry, LoopSubTapestry` is **unchanged**. Connector interfaces become **additively** available at `pirn.connectors.*` (ADR-2). No break here.

**Domain import paths: soft-landing then hard break — Option B → A.**

- **Now (one deprecation cycle):** ship a thin **compatibility shim** inside `pirn-core` at `pirn/domains/<x>.py` (or a `pirn/domains/__init__.py` with lazy `__getattr__`) that, **only if the corresponding `pirn_<x>` package is installed**, re-exports from `pirn_<x>` and emits a `DeprecationWarning`. The shim uses **deferred imports** so `pirn-core` never gains a hard dependency on any domain; if `pirn_<x>` is absent, accessing the shim raises an `ImportError` whose message points at `pip install pirn-<x>`.

  ```python
  # pirn/domains/__init__.py  (in pirn-core)
  _MAP = {"signal": "pirn_signal", "data": "pirn_data", "ml": "pirn_ml",
          "agents": "pirn_agents", "health": "pirn_health", "oilgas": "pirn_oilgas"}
  def __getattr__(name):
      if name in _MAP:
          import importlib, warnings
          warnings.warn(f"`pirn.domains.{name}` is deprecated; import `{_MAP[name]}` instead.",
                        DeprecationWarning, stacklevel=2)
          return importlib.import_module(_MAP[name])
      raise AttributeError(name)
  ```

- **Later (next major):** remove the shim (Option A). Publish a **codemod / `sed` migration guide** (`pirn.domains.<x>` → `pirn_<x>`) shipped with the deprecation note.

- **Optional convenience:** publish Option **C** narrowly — a `pirn[all-domains]` **meta-extra/meta-distribution** that depends on all `pirn-*` packages — for users who genuinely want the monolith ergonomics. It must **not** be the default install (that would defeat isolation), and it is documented as a convenience, not the recommended path.

### Tradeoff chosen

B-then-A balances **clean end-state** (A: no `pirn.domains` surface long-term) against **migration cost** (B: old call sites keep working with a warning for one cycle). The shim's cost — core must know the six domain names and lazy-import them — is small and contained to one module. We reject **C-as-default** because a meta-package that re-exports everything quietly re-creates the monolith and undermines driver #1.

### Deprecation window (open question #3 resolved)

**One minor release** with the shim + `DeprecationWarning`, removal at the **next major** (`1.0`). This pairs with the versioning decision in ADR-6.

---

## ADR-6: Versioning & Release Strategy

### Decision — lockstep now, with an independent-semver exit ramp

- **Through the split and the deprecation window: lockstep.** All eight packages share one version string (bump `pirn-core` and all domains together, e.g. `0.4.0` for the first workspace release). Domain packages pin `pirn-core>=X,<X+1` and (for `pirn-ml`) `pirn-data>=X,<X+1`. A single `uv.lock` and a unified release.
- **Rationale:** during a structural migration, lockstep removes the combinatorial compatibility-matrix problem (`pirn-ml==0.4.0` + `pirn-core==0.3.0`) entirely and keeps CI simple. It also lets us land the `pirn.domains` shim removal as a coordinated **major** bump.
- **Exit ramp (post-`1.0`):** once the surface is stable, allow **independent semver** with a published **compatibility floor** — every domain declares its minimum compatible `pirn-core` (constraint C4), and a compatibility matrix is maintained. This delivers the PRD's "independent release cadence" driver without paying its coordination cost during the risky migration.

### Release pipeline

The build matrix produces **N wheels** (one per package); publish/verify runs per package (testpypi on PR, pypi on main). Version stamping (`calculate_version.py`) applies the shared version to every member's `pyproject.toml` during lockstep; post-`1.0` it stamps per-package.

| Alternative | Reason rejected |
|-------------|-----------------|
| **Independent semver from day one** | Maximizes flexibility but front-loads the compatibility-matrix burden during the exact window when the most cross-package churn happens (interface relocations, shim removal). High risk of version skew. **Deferred to post-1.0.** |

---

## ADR-7: Migration Sequencing (Task-Breakdown Lens)

The split is sequenced so that **each phase is independently mergeable, leaves `main` green, and is reversible**. Detailed Feature→Story→Task breakdown lives in `FEATURES.md`; this is the architectural sequencing and its rationale (dependencies, risk-first).

### Phase 0 — Workspace scaffold (no code moves) — **spike + chore, S–M**
Stand up `[tool.uv.workspace]`, eight `pyproject.toml` skeletons, shared base tool-config (ruff/pyright/pytest), CI matrix skeleton — **while code still lives at `pirn/`**. Validate the empty workspace resolves and builds.
*Dependencies:* none. *Risk-first:* proves the workspace tooling before any move.
**Architectural gate / spike (do first, time-boxed):** verify in a throwaway branch that a domain package calling `Registry.fill_registry(module=__name__, library="pirn")` registers its knots and that bare-name YAML resolves after import. (The `sweet_tea` source read in Context strongly indicates this works; the spike confirms it on real domain code before we commit to R1.)

### Phase 1 — Fold connectors into core — **chore/refactor, L**
Relocate `pirn/domains/connectors` → `packages/pirn-core/src/pirn/connectors/`; promote interfaces to `pirn.connectors.*`; add connector extras to `pirn-core`. **Verify constraint C2** (core imports zero domains; no backend dep at core import time).
*Dependencies:* Phase 0. *Blocking decision (resolved):* ADR-2.

### Phase 2 — Resolve residual edges — **refactor, M**
Relocate `EmbeddingProvider` and `LLMProvider` (+`Tool`) to `pirn.core.providers`; re-point ml/agents/health imports. Confirm package DAG is the tree + single `ml→data` edge (constraints C1, C3).
*Dependencies:* Phase 1. *Blocking decision (resolved):* ADR-3.

### Phase 3 — Extract domains (dependency order) — **refactor, L (per domain)**
Move each domain `pirn/domains/<x>` → `packages/pirn-<x>/src/pirn_<x>`, add its extras and `fill_registry(module=__name__, library="pirn")`. **Order = topological:** `signal` (standalone) → `oilgas` (→core) → `data` (→core) → `ml` (→core,→data) → `agents` (→core) → `health` (→core). Each domain is a separate mergeable PR.
*Dependencies:* Phase 2; `ml` after `data`. *Risk-first:* `signal` first (no edges) de-risks the extraction mechanics before the coupled domains.

### Phase 4 — Compatibility & registry — **feat, M**
Land the `pirn.domains.*` shim + `DeprecationWarning` (ADR-5), the `discover_installed_domains()` helper + loader error message (ADR-4), and migrate tests/examples/docs (`mkdocstrings.paths` → all eight packages) and Docker dependency baking.
*Dependencies:* Phase 3.

### Phase 5 — Independent versioning & publish — **chore, M**
Per-package build matrix → N wheels; publish/verify per package; lockstep version stamping (ADR-6).
*Dependencies:* Phase 4.

**Critical path:** 0 → 1 → 2 → 3(data) → 3(ml) → 4 → 5. `signal`/`oilgas`/`agents`/`health` extractions parallelize within Phase 3 after their dependencies land.

---

## Consequences

### Positive
- **Install isolation achieved:** `pip install pirn-signal` pulls core + scipy/pywavelets/librosa only (success metric verifiable in a clean env).
- **Layering enforced by boundaries + CI** (constraints C1–C4), not convention.
- **Flat dependency graph:** every domain → core, plus a single honest `ml→data` edge.
- **Core public API preserved** (`import pirn` unchanged); connector interfaces become a documented public surface.
- **Independent release cadence** unlocked (post-1.0), with lockstep de-risking the migration.

### Negative / accepted costs
- **The "import the domain to register its knots" rule** is new consumer-facing behaviour; mitigated by docs + `discover_installed_domains()` + better loader errors, but it is a real ergonomic change vs today's single `import pirn`.
- **Core's public contract grows** (connector interfaces + relocated provider interfaces). More surface to keep stable.
- **`pirn.domains.*` breaks** for external consumers; softened by the B→A shim and codemod, but a break nonetheless at the next major.
- **CI complexity grows** (N wheels, per-package extras-isolation); mitigated by change-detection gates and a shared base config, but more pipeline to maintain.
- **`pirn-ml` always pulls `pirn-data`** — you cannot install ml without data. Accepted as semantically correct.

### Verification hooks (turn metrics into CI checks)
- Import-graph check: C2 (core→no domain) and the no-backend-dep-at-core-import rule.
- Topological check: C1/C3 (acyclic; exactly one domain→domain edge).
- Clean-env install + dependency-tree assertion per domain: install isolation.
- Cross-domain tapestry (data+ml+agents) resolves all knots by name after importing the packages: registry parity (R1).

---

## Open Questions — Resolutions

| # | Question | Resolution |
|---|----------|-----------|
| 1 | Residual edges: break or declare? | `agents→ml` **break** (`EmbeddingProvider`→core); `health→agents` **break** (`LLMProvider`→core); `ml→data` **declare** `pirn-ml→pirn-data`. (ADR-3) |
| 2 | `sweet_tea` registry semantics | **Verified by source read.** `fill_registry()` scans the caller's dir (or `module=` if passed); `library` is an explicit kwarg; missing-dep modules are skipped with a warning. Keys are the **lowercased class name**, and a bare-name lookup **raises** on >1 entry — so the 5 existing key collisions (B1) MUST be resolved (consolidate/rename) before R1. Pass `module=__name__, library="pirn"` from each domain. (ADR-4) |
| 3 | Blast-radius window | Shim (Option B) for **one minor**, hard break (A) at **next major (1.0)**; publish C only as opt-in `pirn[all-domains]`. (ADR-5) |
| 4 | Versioning policy | **Lockstep** through migration + deprecation window; **independent semver post-1.0** with a compatibility floor + matrix. (ADR-6) |
| 5 | Connectors naming/identity | Namespaced public surface `pirn.connectors.*` (not flattened); `PirnOpaqueValue`/`DataTransport`/`SerializerRegistry` stay on their existing `pirn.core.*` paths. (ADR-2) |
| 6 | Cross-package test/conftest | Centralize shared fixtures in `pirn-core` (importable test-support module) rather than a separate `pirn-test-support` package, until fixture sharing proves it needs its own wheel. (Sequenced in Phase 4; FEATURES details.) |
