# Migrating to Split Packages

pirn's six domains used to live inside the `pirn` distribution under
`pirn.domains.<x>`. As of the split-core-and-domains work (Phase 3) each domain
ships as its **own standalone distribution** that imports under a `pirn_<x>`
name. This guide explains the change, the automated codemod that rewrites your
imports, the full module mapping, the deprecation window, and the opt-in
`all-domains` convenience for callers who want the old monolith ergonomics.

---

## Why the split

The monolith forced every install to drag along the heavy, mutually-exclusive
dependency trees of all six domains. Splitting lets you:

- install only the domains you use (`pip install pirn-signal` instead of
  pulling DICOM, segyio, and Spark you will never touch);
- version and release each domain's heavy deps independently;
- keep `pirn-core` dependency-free of any domain (constraint C2), so the
  framework stays small and fast to install.

`pirn-core` keeps the framework primitives and the connector surface
(`pirn.connectors.*`); the domains move out:

| Layer | Distribution | Imports as |
|-------|-------------|-----------|
| Framework + connectors | `pirn-core` | `pirn` |
| Data domain | `pirn-data` | `pirn_data` |
| ML domain | `pirn-ml` | `pirn_ml` |
| Signal domain | `pirn-signal` | `pirn_signal` |
| Agents domain | `pirn-agents` | `pirn_agents` |
| Health domain | `pirn-health` | `pirn_health` |
| Oil & Gas domain | `pirn-oilgas` | `pirn_oilgas` |

---

## Module mapping

Replace every legacy `pirn.domains.<x>` import with the standalone `pirn_<x>`
package, and install the matching distribution:

| Legacy import | New import | Install |
|---------------|-----------|---------|
| `pirn.domains.signal` | `pirn_signal` | `pip install pirn-signal` |
| `pirn.domains.data` | `pirn_data` | `pip install pirn-data` |
| `pirn.domains.ml` | `pirn_ml` | `pip install pirn-ml` |
| `pirn.domains.agents` | `pirn_agents` | `pip install pirn-agents` |
| `pirn.domains.health` | `pirn_health` | `pip install pirn-health` |
| `pirn.domains.oilgas` | `pirn_oilgas` | `pip install pirn-oilgas` |

The submodule path below the top level is unchanged — only the prefix moves.
For example:

```python
# before
from pirn.domains.data.sources.file_source import FileSource
from pirn.domains.signal.filters.butterworth_filter import ButterworthFilter

# after
from pirn_data.sources.file_source import FileSource
from pirn_signal.filters.butterworth_filter import ButterworthFilter
```

Each domain depends on `pirn-core`; `pirn-ml` additionally depends on
`pirn-data` (the one retained domain→domain edge, ADR-3), so installing
`pirn-ml` pulls `pirn-data` automatically. Most domains also expose extras for
their heavy backends — e.g. `pip install 'pirn-data[polars]'`,
`pip install 'pirn-signal[signal]'`, `pip install 'pirn-health[health]'`. See
each [domain page](../domains/index.md) for the full extra list.

---

## Registration still works the same way

Importing a domain package self-registers its knots under `library="pirn"`, so
a YAML pipeline keeps resolving them by **bare name** (ADR-4). A plain
`import pirn_data` triggers the package's `Registry.fill_registry()`; nothing
else changes. To register every installed domain in one call (handy for
YAML-only deployments), use the core helper:

```python
import pirn

pirn.discover_installed_domains()   # imports every installed pirn_<x>
```

---

## Automated codemod: `pirn-migrate-imports`

`pirn-core` ships a deterministic, idempotent codemod that rewrites legacy
imports for you. It is installed as the `pirn-migrate-imports` console script:

```bash
# Rewrite in place across your source tree (directories are walked recursively).
pirn-migrate-imports src/ tests/

# Dry run — report which files would change and exit non-zero if any do.
# Wire this into CI to fail builds that still use the legacy paths.
pirn-migrate-imports --check src/ tests/
```

You can also invoke it as a module if the script is not on your `PATH`:

```bash
python -m pirn._migrate.main src/ tests/
python -m pirn._migrate.main --check src/ tests/
```

What it does:

- Rewrites `import pirn.domains.<x>` and `from pirn.domains.<x> import …`
  (and `from pirn.domains.<x>.<sub> import …`) to the corresponding
  `pirn_<x>` form, for all six domains.
- Is **idempotent** — running it twice produces no further changes — and
  **deterministic**: output is a sorted, stable summary, so the same input
  always yields the same result.
- Accepts one or more files or directories; directories are walked recursively
  for `.py` files.

Review the diff and run your test suite after rewriting. The codemod only
touches import statements; it does not change runtime behaviour.

---

## Deprecation window

The legacy `pirn.domains.*` paths still resolve through a compatibility shim:
each `pirn.domains.<x>` access defers to the installed `pirn_<x>` package and
emits a `DeprecationWarning`. The shim:

- **lives for one minor release** and is **removed at the next major (1.0)**;
- works only when the backing `pirn_<x>` distribution is installed — if it is
  absent, you get an actionable `ImportError` naming the package to install;
- keeps `pirn-core` free of any hard domain dependency (resolution is fully
  deferred at import time), so the warning is the only behavioural change.

Migrate before 1.0. To surface the warnings during development, run Python with
`-W error::DeprecationWarning` (or pytest with
`filterwarnings = error::DeprecationWarning`) so any remaining legacy import
fails loudly.

---

## Optional: `pirn-core[all-domains]` for monolith ergonomics

If you want the old "everything in one install" feel, the opt-in
`all-domains` extra on `pirn-core` pulls all six domain distributions at once
(ADR-5 Option C):

```bash
pip install 'pirn-core[all-domains]'
```

This installs `pirn-signal`, `pirn-oilgas`, `pirn-data`, `pirn-ml`,
`pirn-agents`, and `pirn-health` (each pulling `pirn-core`). It is
**explicitly not the default install** — `pip install pirn-core` stays
domain-free so the base framework remains small (constraint C2). `all-domains`
pulls the domain *packages* but not their heavy per-domain backend extras; add
those as needed, e.g. `pip install 'pirn-data[polars]' 'pirn-health[health]'`.

After installing, register everything in one call:

```python
import pirn

pirn.discover_installed_domains()
```

---

**See also:** [Domains overview](../domains/index.md),
[Knot Registration](knot-registration.md),
[YAML Pipelines](yaml-pipelines.md)
