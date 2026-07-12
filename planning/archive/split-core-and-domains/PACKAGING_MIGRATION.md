# Packaging Migration: Single Hatch Wheel → uv Workspace

**Status:** Planning — 2026-06-09
**Owner:** devops-agent
**Tracking Issue:** [#51](https://github.com/snoodleboot-io/pirn/issues/51)
**Companion docs:** `PRD.md`, `ADR.md`, `FEATURES.md` (this directory)
**Scope:** Planning only. This is the concrete devops execution plan that the FEATURES items (`SCD-02`, `SCD-03`, and the Phase 3–5 packaging tasks) implement. No source is moved, renamed, or refactored by this document.

---

## 0. Goal & the constraint that shapes everything

Move `pirn` from **one** Hatch wheel (`pirn` 0.3.0, `packages=["pirn"]`) to a **uv workspace** of **eight** independently-installable wheels:

| dist name | imports as | hard deps (intra-workspace) | heavy deps |
|-----------|-----------|------------------------------|------------|
| `pirn-core` | `pirn` | — (only `sweet_tea`) | connector/backend extras (optional) |
| `pirn-signal` | `pirn_signal` | `pirn-core` | scipy, pywavelets, librosa |
| `pirn-data` | `pirn_data` | `pirn-core` | pandas, pyarrow (+ tier extras) |
| `pirn-ml` | `pirn_ml` | `pirn-core`, **`pirn-data`** | numpy, pandas, scikit-learn |
| `pirn-agents` | `pirn_agents` | `pirn-core` | — (user-supplied) |
| `pirn-health` | `pirn_health` | `pirn-core` | pydicom, mne, nibabel, … |
| `pirn-oilgas` | `pirn_oilgas` | `pirn-core` | segyio, lasio, resfo |

**The single hardest devops fact:** today CI relies on a *pre-baked Docker venv* (`pirn-ci-base:py$V`, built from the **root `pyproject.toml`**) holding every extra, and on `uv sync --all-extras` resolving **one** project. After the split there is no single project — there is a workspace with one `uv.lock`. Every CI job, every Dockerfile, every publish step that names "pirn" or "the wheel" must become package-aware. The plan below keeps the lockstep version (ADR-6) and the pre-baked-image model, and changes them additively so **`main` stays green at every merge** (ADR-7 sequencing).

---

## 1. Target on-disk layout (devops-relevant files only)

```
pirn/                                     # workspace root
├── pyproject.toml                        # [tool.uv.workspace] ONLY — not a published wheel
├── uv.lock                               # ONE lock for the whole workspace
├── ruff.toml                             # shared lint config (root)
├── packages/
│   ├── pirn-core/pyproject.toml          # build + core extras + tool overrides
│   ├── pirn-signal/pyproject.toml
│   ├── pirn-data/pyproject.toml
│   ├── pirn-ml/pyproject.toml
│   ├── pirn-agents/pyproject.toml
│   ├── pirn-health/pyproject.toml
│   └── pirn-oilgas/pyproject.toml
├── tests/                                # stays centralized (ADR open-q #6)
├── examples/  docs/  mkdocs.yml
├── Dockerfile.ci  Dockerfile.ci-heavy
├── docker-compose.test.yml
└── .github/workflows/*.yml  .github/scripts/*
```

`src/` layout (ADR-1) is mandatory: it forces every test/CI job to run against the **installed** wheel, which is exactly how install-isolation (driver #1) is verified — you physically cannot import a domain that wasn't declared a dependency.

---

## 2. Root workspace `pyproject.toml`

The root is **not** a published distribution (no `[build-system]`, no wheel target). It only wires the workspace and holds the shared dev group + shared tooling defaults.

```toml
# ./pyproject.toml  (workspace root — NOT published)
[tool.uv.workspace]
members = ["packages/*"]

# Resolve intra-workspace deps to local source during dev/CI (never PyPI).
[tool.uv.sources]
pirn-core   = { workspace = true }
pirn-signal = { workspace = true }
pirn-data   = { workspace = true }
pirn-ml     = { workspace = true }
pirn-agents = { workspace = true }
pirn-health = { workspace = true }
pirn-oilgas = { workspace = true }

# Dev/CI convenience: install the whole workspace in editable mode.
[dependency-groups]
dev = [
  "pytest>=8.0", "pytest-asyncio>=0.23", "pytest-cov>=4.0",
  "pytest-benchmark>=5.2.3", "pytest-timeout>=2.4.0",
  "mutmut>=2.5,<4", "ruff>=0.5", "pyright>=1.1",
  "cyclonedx-bom>=4.0", "pre-commit>=4.6.0",
]
all = ["pirn-core", "pirn-signal", "pirn-data", "pirn-ml",
       "pirn-agents", "pirn-health", "pirn-oilgas"]
```

> **`uv sync` semantics in a workspace:** running `uv sync` at the root installs **all** members editable into one `.venv` against the single `uv.lock`. `uv sync --package pirn-data` installs just that member (+ its transitive workspace deps). `uv build --package pirn-data` builds one wheel. These three commands replace today's monolithic `uv sync --all-extras` / `uv build`.

---

## 3. Per-package `pyproject.toml` templates

### 3a. `packages/pirn-core/pyproject.toml`

Core keeps `sweet_tea` as its **only** hard dep and absorbs **all** connector/backend/file-format extras (ADR-2). The `[project.scripts]` entry points (`tapestry-check`, `pirn-explore`) move here — they live in `pirn.check` / `pirn.viz`, which are core.

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pirn-core"
version = "0.4.0"                         # lockstep (ADR-6); stamped by CI
description = "pirn core — a pipeline framework where everything is a knot."
requires-python = ">=3.11"
license = { text = "Apache-2.0" }
dependencies = [
  "cloudpickle>=3.0",
  "numpy>=2.4.4",                         # core serializer registers numpy conditionally
  "pydantic>=2.0",
  "pyyaml>=6.0",
  "sweet-tea>=0.2.46",
]

[project.scripts]
tapestry-check = "pirn.check.main:main"
pirn-explore   = "pirn.viz._explore_cli:main"

[project.optional-dependencies]
# ── ALL connector / backend / codec extras fold in here (ADR-2) ──
# (verbatim move of today's root extras; abbreviated — full list = current
#  pyproject lines 50–414 minus the 6 DOMAIN extras data/ml/health/signal/oilgas/mri)
sqlite = ["aiosqlite>=0.19"]
postgres = ["asyncpg>=0.31"]
duckdb = ["duckdb>=0.10"]
s3 = ["aioboto3>=12.0"]
# … gcs, azure, kafka, valkey, mysql, bigquery, snowflake, …
zstd = ["zstandard>=0.22"]; snappy = ["python-snappy>=0.7"]; lz4 = ["lz4>=4.3"]
all-db = [ "..." ]; all-storage = [ "..." ]; all-stream = [ "..." ]
docs = ["mkdocs>=1.6", "mkdocstrings[python]>=0.25", "pymdown-extensions>=10.0",
        "mkdocs-section-index>=0.3", "playwright>=1.44"]

[tool.hatch.build.targets.wheel]
packages = ["src/pirn"]                   # imports as `pirn`

# Tool overrides (see §4): include path is THIS package's source only.
[tool.pyright]
include = ["src/pirn"]
reportMissingImports = false
reportMissingModuleSource = false
reportIncompatibleMethodOverride = "none"
```

### 3b. `packages/pirn-signal/pyproject.toml` — template for every domain

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pirn-signal"
version = "0.4.0"
requires-python = ">=3.11"
license = { text = "Apache-2.0" }
dependencies = ["pirn-core>=0.4.0,<0.5.0"]   # lockstep floor (ADR-6 / constraint C4)

[project.optional-dependencies]
signal = ["scipy>=1.12", "pywavelets>=1.5", "librosa>=0.10"]
emd    = ["EMD-signal>=1.6", "scipy>=1.12"]

[tool.hatch.build.targets.wheel]
packages = ["src/pirn_signal"]

[tool.pyright]
include = ["src/pirn_signal"]
reportMissingImports = false
reportIncompatibleMethodOverride = "none"
```

**Per-domain deltas from the template** (extras lifted verbatim from the current root pyproject):

| package | `dependencies` | domain extras moved in |
|---------|----------------|------------------------|
| `pirn-data` | `pirn-core` | `data`, + tier extras `polars/datafusion/ibis/spark/ray-data/modin/pathway/bytewax/lance/eland/delta/iceberg/all-frames/all-lazy/pandera/great-expectations` |
| `pirn-ml` | `pirn-core`, **`pirn-data>=0.4.0,<0.5.0`** | `ml`, + ML-artefact format extras `onnx/safetensors/joblib/pytorch/tensorflow/gguf/tflite` |
| `pirn-agents` | `pirn-core` | `agents` (empty — user-supplied providers) |
| `pirn-health` | `pirn-core` | `health`, `mri`, `genomics`, `bids`, `pyteomics` |
| `pirn-oilgas` | `pirn-core` | `oilgas` |

> **Extra-ownership rule:** an extra lives on the package whose code imports the dependency. Backend/codec extras (postgres, s3, hdf5, fits, …) are imported by `pirn/connectors/*` → they go on **`pirn-core`**. `pandas`/`pyarrow` (data domain) → `pirn-data`. `scikit-learn` → `pirn-ml`. The `heavy` markers `pytorch/tensorflow/tflite` stay format-codec extras on the package that decodes them (ml artefacts → `pirn-ml`; but note Dockerfile.ci excludes them from the base image regardless — §6).

---

## 4. Shared vs per-package tool config (ruff / pyright / pytest)

Goal: **one source of truth** for rules, **per-package scoping** only where the tool needs a path. Avoids config drift (risk from Discovery).

| tool | strategy | where |
|------|----------|-------|
| **ruff** | **Fully shared.** One `ruff.toml` at the repo root; ruff auto-discovers it for every package. No per-package ruff config. Keep the per-file ignores (`pirn/__init__.py` RUF022, viz E501) — update globs to `**/pirn/__init__.py`, `**/pirn/viz/*.py`. | root `ruff.toml` |
| **pyright** | **Shared base + per-package `include`.** pyright cannot union-scan independently-installed packages cleanly, so each package's `pyproject.toml` carries a tiny `[tool.pyright]` with `include = ["src/<pkg>"]` and inherits the shared rule set (the three `report*` toggles). CI runs pyright **per package** in its own synced env. | per-package `[tool.pyright]` |
| **pytest** | **Shared, centralized.** Tests stay in root `tests/` (ADR open-q #6). Keep `[tool.pytest.ini_options]` + all markers in the **root** `pyproject.toml`'s `[tool.pytest.ini_options]` is not valid on a non-project root → move it to a root **`pytest.ini`** (or `tool.pytest` in a stub). Shared conftest fixtures live in `pirn-core` as an importable `pirn._testsupport` module (ADR open-q #6), imported by domain test conftests. | root `pytest.ini` + `pirn._testsupport` |
| **mutmut** | Per-package `paths_to_mutate`. Root `pytest.ini` cannot hold `[tool.mutmut]` for 8 trees; CI passes `--paths-to-mutate packages/<pkg>/src` per changed package. | CI-driven |

Example shared `ruff.toml`:

```toml
# ./ruff.toml  (shared by every workspace member)
line-length = 100
target-version = "py311"
exclude = ["tests/", "scripts/"]

[lint]
select = ["E", "F", "I", "B", "UP", "RUF"]
ignore = ["E501"]

[lint.per-file-ignores]
"**/pirn/__init__.py" = ["RUF022"]
"**/pirn/viz/explorer.py" = ["E501"]
"**/pirn/viz/html.py" = ["E501"]
"tests/**/*.py" = ["F841"]
```

---

## 5. CI workflow changes

Design principle: **one matrix dimension added (`package`), change-detection gates, shared cache.** Do not multiply the existing 4-Python × 6-suite matrix by 8 packages blindly (that is the 192-job explosion risk). Lint/type-check go per-package; the **test suites stay whole-workspace** (one synced env runs all of `tests/`), because tests are centralized and a cross-domain tapestry must resolve knots from several packages at once (registry-parity check, ADR-4 R1).

### 5a. Build matrix → N wheels

Replace the single `build-release` `uv build` with a package matrix:

```yaml
build-release:
  strategy:
    fail-fast: false
    matrix:
      package: [pirn-core, pirn-signal, pirn-data, pirn-ml,
                pirn-agents, pirn-health, pirn-oilgas]
  steps:
    - uses: actions/checkout@... { fetch-depth: 0 }
    - uses: astral-sh/setup-uv@...  { enable-cache: true, python-version: "3.12" }
    - name: Calculate version
      id: version
      run: python .github/scripts/calculate_version.py        # see §7
      env: { PACKAGE_NAME: ${{ matrix.package }}, ... }
    - name: Stamp version (all members, lockstep)
      run: python .github/scripts/stamp_version.py ${{ steps.version.outputs.version }}
    - name: Build one wheel
      run: uv build --package ${{ matrix.package }}
    - name: Verify installability (clean env, isolation)
      run: |
        python -m venv .verify && . .verify/bin/activate
        pip install "dist/${MATRIX_PKG_WHEEL}"                 # pulls pirn-core from index
        python -c "import ${{ matrix.package }}".replace('-','_')
    - uses: actions/upload-artifact@... { name: dist-${{ matrix.package }}, path: dist/ }
```

**Install-graph note:** `pip install dist/pirn_signal-*.whl` in a clean env must pull `pirn-core` **from the index**, not the workspace — so feature-branch verify jobs need `pirn-core` already on TestPyPI, or use `--find-links dist/` with all wheels present. Decision: feature-branch verify downloads **all** package artifacts and `pip install --find-links dist/ pirn-<pkg>` so the local dep graph resolves without hitting an index (matches ADR-6 lockstep).

### 5b. Lint / type-check per package

```yaml
lint:
  strategy: { matrix: { package: [pirn-core, pirn-signal, ...] } }
  container: { image: ghcr.io/.../pirn-ci-base:py3.12 }
  steps:
    - uses: actions/checkout@...
    - run: uv sync --package ${{ matrix.package }}              # member + its workspace deps
    - run: uv run ruff check  --output-format=github packages/${{ matrix.package }}/src
    - run: uv run ruff format --check packages/${{ matrix.package }}/src
    - run: uv run pyright packages/${{ matrix.package }}/src
```

Add a **change-detection** pre-job (`dorny/paths-filter`) so a PR touching only `packages/pirn-signal/**` runs lint/pyright for `pirn-core` (always, it's the dependency) + `pirn-signal` only.

### 5c. Test / coverage matrix

Keep the existing suites (`unit / integration / smoke / e2e / perf`) **whole-workspace** in one synced env — this is the cheapest correct option and preserves cross-domain registry tests:

```yaml
unit-tests:
  strategy: { matrix: { python-version: ["3.11","3.12","3.13","3.14"] } }
  container: { image: ghcr.io/.../pirn-ci-base:py${{ matrix.python-version }} }
  steps:
    - uses: actions/checkout@...
    - run: uv sync --all-packages --all-extras --no-extra pytorch --no-extra tensorflow --no-extra tflite
    - run: uv run python -m pytest tests/unit
             --cov=pirn --cov=pirn_signal --cov=pirn_data --cov=pirn_ml
             --cov=pirn_agents --cov=pirn_health --cov=pirn_oilgas
             --cov-report=xml --junitxml=test-results/unit-${{ matrix.python-version }}.xml
```

- `--all-packages` (uv) installs every workspace member editable in one env.
- **Coverage** now needs one `--cov=<import_name>` per package (7 flags) because they are distinct top-level packages. Codecov upload (py3.12 only) unchanged otherwise.
- **Per-package install-isolation** moves into the rewritten `extras-isolation` job (§5d) — that is where "ml can't import without data, signal needs nothing else" is actually asserted.

### 5d. Rewrite `extras-isolation` → real install-isolation (clean env per package)

Today this job does `pip install -e ".[data]"; import pirn.domains.data`. After the split it becomes the **primary verification hook** for driver #1 (ADR Consequences "Verification hooks"). Each step uses a **fresh venv** and asserts the dependency tree:

```yaml
isolation:
  steps:
    - name: "pirn-signal pulls core + scipy only (NOT data/ml/health)"
      run: |
        python -m venv .v && . .v/bin/activate
        uv pip install --find-links dist/ "pirn-signal[signal]"
        python -c "import pirn_signal; import pirn"          # works
        ! python -c "import pirn_data"  2>/dev/null          # MUST fail — not installed
        pip list | grep -qE 'pirn-data|pandas' && exit 1 || true
    - name: "pirn-ml transitively installs pirn-data (declared edge)"
      run: |
        python -m venv .v && . .v/bin/activate
        uv pip install --find-links dist/ "pirn-ml[ml]"
        python -c "import pirn_ml, pirn_data"               # data pulled in
    - name: "agents/health no longer pull ml/agents (edges broken, ADR-3)"
      run: |
        python -m venv .v && . .v/bin/activate
        uv pip install --find-links dist/ "pirn-agents"
        ! python -c "import pirn_ml" 2>/dev/null             # MUST fail
```

Plus the **import-graph constraint checks** (ADR constraints C1–C3) as a standalone job:

```yaml
import-graph:
  steps:
    - run: uv sync --all-packages
    - name: C2 — core imports zero pirn_<domain>
      run: python scripts/check_import_graph.py --core-is-sink
    - name: C1/C3 — DAG, exactly one domain→domain edge (ml→data)
      run: python scripts/check_import_graph.py --acyclic --max-domain-edges 1
    - name: no backend dep imported at `import pirn` time
      run: python scripts/check_import_graph.py --no-backend-at-core-import
```

### 5e. Connector extras isolation

The current 30-step connector-extras loop (postgres/s3/kafka/…) keeps the **same shape** but targets `pirn-core` (connectors folded in):

```yaml
- name: "[postgres] install + import"
  run: |
    python -m venv .v && . .v/bin/activate
    uv pip install --find-links dist/ "pirn-core[postgres]"
    python -c "import pirn.connectors; print('OK: postgres')"
```

### 5f. Caching

- **uv cache:** `setup-uv` with `enable-cache: true` keyed on the **single root `uv.lock`** — unchanged, and *better* than today because one lock covers all members (no per-package lock fan-out).
- **Docker layer cache:** `cache-from/to: type=gha` per Python version — unchanged.
- **Change-detection** (`dorny/paths-filter`) gates the build/lint matrices so untouched packages skip — the main lever against CI-time blowup.

### 5g. mutation / heavy / real-backends

- **mutation.yml:** swap `--paths-to-mutate pirn/` → resolve changed package(s) and pass `packages/<pkg>/src`; `--runner` stays `pytest tests/unit`. Nightly full run iterates all 7 `packages/*/src`.
- **heavy-tests.yml / real-backends.yml:** only change is `uv pip install --system -e .` → `uv sync --all-packages --all-extras` (or `uv pip install --find-links dist/ "pirn-ml[pytorch]"` for heavy). Services in `docker-compose.test.yml` / job `services:` unchanged — connectors are now core, the Postgres/Valkey/Kafka/MinIO fixtures are identical.

---

## 6. Docker CI images

The pre-baked-venv model **survives**, but the build context changes from "copy root `pyproject.toml`" to "copy the **whole workspace**" because `uv sync` now needs every member's `pyproject.toml` + the root workspace table to resolve.

```dockerfile
# Dockerfile.ci  (revised)
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim
# ... apt build deps (gfortran, libgdal, ffmpeg, …) UNCHANGED ...
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /opt/pirn-deps
# Need the workspace table + every member's manifest so the lock resolves.
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/                       # manifests (+ minimal src for editable)
ENV UV_PYTHON_PREFERENCE=only-system \
    UV_PROJECT_ENVIRONMENT=/opt/pirn-deps/.venv

# Pre-build ALL members' deps; exclude heavy ML codecs (baked by ci-heavy).
RUN uv sync --all-packages --all-extras --no-install-project \
      --no-extra pytorch --no-extra tensorflow --no-extra tflite && \
    rm -f uv.lock
```

> **`--no-install-project` with a workspace:** uv installs the dependency closure of all members but not the members themselves (they're installed at job runtime via checkout). To make `COPY packages/` cheap, copy only the `pyproject.toml`s (not full `src/`) — a `.dockerignore` or a two-stage copy that brings in `packages/*/pyproject.toml` keeps the layer small and cache-stable. `Dockerfile.ci-heavy` is unchanged except it inherits the new base and runs `uv sync --all-packages --all-extras` (adds torch/tensorflow on top).

**`build-ci-image.yml`** trigger `paths:` must add `packages/**/pyproject.toml` and `uv.lock` (so an extras change in any member rebuilds the base image), alongside the existing `Dockerfile.ci*` / root `pyproject.toml` triggers.

---

## 7. Publishing each package

Lockstep through the migration (ADR-6): **one version string, N wheels, per-package publish.**

- **Version source:** keep `calculate_version.py` but call it **once** to produce the shared version (PyPI floor query uses `pirn-core` as the canonical package). A new `stamp_version.py` writes that string into **all 7** `packages/*/pyproject.toml` (replacing the single `sed` on root). `pirn-ml`/domains' `>=X,<X+1` core floor is regenerated from the same string.
- **Publish matrix:** `publish-testpypi` / `publish-pypi` gain `strategy.matrix.package` and download `dist-${{ matrix.package }}`, publishing each wheel under its own PyPI project. Trusted-publishing (`id-token: write`, `pypa/gh-action-pypi-publish`) is configured **per PyPI project** — 7 projects must each have a publisher binding to this repo/workflow. `skip-existing: true` on TestPyPI unchanged.
- **Publish order:** `pirn-core` **first** (domains depend on it); then domains in parallel. Enforce with `needs:` so a domain wheel never lands on PyPI referencing a core version that isn't published yet.
- **Verify:** `verify-pypi` installs the **meta convenience** `pirn[all-domains]` (ADR-5 Option C) in a clean env and asserts `import pirn` + each `import pirn_<domain>` + `tapestry-check --help`, plus one isolation check (`pip install pirn-signal` alone). Index-propagation `sleep 60` + retry loop unchanged.
- **First cutover release:** publish all 7 at `0.4.0`. The legacy `pirn` 0.3.x project on PyPI becomes the **meta-distribution** `pirn` (`all-domains` extra, ADR-5 C) at `0.4.0`, so `pip install pirn` keeps working (monolith ergonomics, opt-in).

---

## 8. Docs build under mkdocs

`mkdocstrings.paths: [pirn]` only sees core after the split. Two changes:

```yaml
# mkdocs.yml
plugins:
  - mkdocstrings:
      handlers:
        python:
          paths: [packages/pirn-core/src, packages/pirn-signal/src,
                  packages/pirn-data/src, packages/pirn-ml/src,
                  packages/pirn-agents/src, packages/pirn-health/src,
                  packages/pirn-oilgas/src]
```

- **`docs.yml`** install step `uv sync --extra docs` → `uv sync --all-packages --extra docs` (the `docs` extra lives on `pirn-core` per §3a; `--all-packages` ensures every domain is importable so mkdocstrings can introspect it). The domain nav pages (`domains/*.md`, `connectors/index.md`) are unchanged in structure; their autodoc `::: pirn_<domain>.…` directives switch from `pirn.domains.<x>` to `pirn_<x>` — a mechanical doc edit landed in Phase 4 alongside the import codemod.
- Connectors doc page now documents `pirn.connectors.*` (core public surface, ADR-2) rather than a domain.

---

## 9. Rollout — keep CI green at every step

Mapped to ADR-7 phases; each row is an independently-mergeable PR that leaves `main` green. The trick is **additive scaffolding before any move**, and a **temporary dual-path** where CI tolerates both `pirn/` (old) and `packages/` (new) until the last move lands.

| Step | What changes | Why CI stays green |
|------|--------------|--------------------|
| **R0 — spike** (SCD-01) | Throwaway branch only; verify `fill_registry(module=, library="pirn")`. | No change to `main`. |
| **R1 — workspace scaffold** | Add root `[tool.uv.workspace]` + 7 **empty** `packages/*/pyproject.toml` (no src). Code still at `pirn/`. Add `ruff.toml`, `pytest.ini`. CI: add a *non-blocking* `workspace-resolves` job (`uv lock --check`, `uv sync --all-packages`). Existing jobs untouched (still build the root `pirn` wheel). | Old monolith build/test path is unchanged; new job is informational. |
| **R2 — Docker base accepts workspace** | Update `Dockerfile.ci*` to copy `packages/*/pyproject.toml` + run `uv sync --all-packages`. Rebuild images. Workspace is empty so the synced set == today's deps. | Image content identical (empty members add no deps); all jobs still pass. |
| **R3 — fold connectors into core** | Move `pirn/domains/connectors` → `packages/pirn-core/src/pirn/connectors/`; **but** keep `pirn/` as the live tree via a transitional symlink/path so old `import pirn.domains.connectors` still resolves through the shim (ADR-5). CI gains the C2 / no-backend-at-import import-graph check. | Public `pirn` import unchanged; shim covers old connector path. |
| **R4 — resolve residual edges** | Relocate `EmbeddingProvider` / `LLMProvider` to `pirn.core.providers`; re-point imports. Add C1/C3 import-graph check (expect 1 edge). | Behaviour-preserving moves; tests unchanged. |
| **R5 — extract domains (topo order)** | One PR per domain: move `pirn/domains/<x>` → `packages/pirn-<x>/src/pirn_<x>`, add extras + `fill_registry(module=__name__, library="pirn")`, land `pirn.domains.<x>` deprecation shim. Order: signal → oilgas → data → ml → agents → health. **Each PR flips that domain's CI from monolith to workspace install** and adds its isolation step. | Shim keeps `import pirn.domains.<x>` working; the rest of the monolith still builds; only the moved domain switches install path. |
| **R6 — switch CI to package matrices** | Replace monolith `build-release`/`lint` with the §5 matrices; drop the old root-wheel build; rewrite `extras-isolation`; update `mkdocs.yml` paths; `mutation.yml` per-package. | All moves are done; matrices now have real members to build. The meta `pirn[all-domains]` keeps verify/docs green. |
| **R7 — publish split** | Per-package publish matrix (§7); first `0.4.0` cutover; legacy `pirn` becomes the meta-dist. Deprecation window opens (ADR-5: shim for one minor, removed at 1.0). | `pirn-core` publishes before domains (`needs:`); verify installs both isolated and meta forms. |

**Reversibility:** R3–R5 each keep the `pirn.domains.*` shim, so any single PR can be reverted without breaking downstream imports. R6 is the irreversible "flip" — gated behind every domain having landed in R5.

---

## 10. New devops artifacts to create (deliverables for Phase 5 issues)

| file | purpose |
|------|---------|
| `pyproject.toml` (root, rewritten) | workspace table + dev group only |
| `packages/*/pyproject.toml` (×7) | per §3 templates |
| `ruff.toml`, `pytest.ini` | shared lint/test config (§4) |
| `.github/scripts/stamp_version.py` | write one version into all 7 manifests + core floors (§7) |
| `scripts/check_import_graph.py` | C1/C2/C3 + no-backend-at-core-import enforcement (§5d) |
| revised `Dockerfile.ci` / `Dockerfile.ci-heavy` | workspace-aware pre-bake (§6) |
| revised `.github/workflows/{ci,build-ci-image,docs,mutation,heavy-tests,real-backends}.yml` | package matrices + change detection (§5) |

---

## Summary

Move the single Hatch wheel to a uv workspace of 8 wheels (`pirn-core` imports as `pirn`; six `pirn-<domain>`), wired by `[tool.uv.workspace]` + `[tool.uv.sources]` with one `uv.lock`. Ruff config is fully shared (root `ruff.toml`); pyright/pytest are shared-rules + per-package `include`; tests stay centralized with fixtures in `pirn-core`. CI adds a `package` matrix dimension for build + lint (gated by change-detection to avoid a job explosion) while test suites stay whole-workspace via `uv sync --all-packages`; coverage takes one `--cov=` flag per import name; a rewritten `extras-isolation` job + an `import-graph` job become the real verification hooks for install isolation and the acyclic DAG. Docker pre-baked images copy the whole workspace and `uv sync --all-packages`; docs add all 7 `src` paths to `mkdocstrings`. Publishing is lockstep (one version, N wheels), `pirn-core` first, with the legacy `pirn` project repurposed as an opt-in `all-domains` meta-distribution. Rollout is additive (scaffold → docker → fold → edges → per-domain extraction behind shims → flip CI → split publish), keeping `main` green at every PR.

### Top CI risks
1. **Job-count explosion (192-job trap):** 8 packages × 4 Python × 6 suites. Mitigation: lint/build go per-package; **test suites stay whole-workspace** (one synced env), and change-detection (`dorny/paths-filter`) skips untouched packages.
2. **Pre-baked Docker image drift:** the base image is built from a frozen `pyproject` copy; after the split it must copy **all** members' manifests + `uv lock` or the synced venv silently diverges from what jobs install. Image build trigger must watch `packages/**/pyproject.toml` + `uv.lock`.
3. **Install-graph / index ordering on publish:** a domain wheel published before `pirn-core` (or before its `>=X,<X+1` floor exists on PyPI) makes `pip install pirn-ml` unresolvable. Mitigation: `needs: publish-core`, and feature-branch verify uses `--find-links dist/` so the local graph resolves without an index.
4. **Registry parity in CI (ADR-4 R1):** cross-domain tapestry tests only pass if every domain package is imported so its knots self-register under `library="pirn"`. The whole-workspace `uv sync --all-packages` test env preserves this; a naively per-package test split would break bare-name YAML resolution.
5. **Coverage fragmentation:** distinct top-level packages mean coverage no longer rolls up under one `--cov=pirn`; missing a `--cov=pirn_<domain>` flag silently drops a package from the Codecov number. Enforce all 7 flags in the unit-test job and assert combined-report package count.
6. **Trusted-publishing × 7 projects:** each new PyPI project needs its own OIDC publisher binding; a missing binding fails the publish matrix only at release time (not on PRs), so it must be provisioned during R7 before the first `0.4.0` cutover.
