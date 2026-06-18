# Domains

Domain-specific knot libraries built on top of pirn's core pipeline primitives.

## Standalone packages

As of the split-core-and-domains work (Phase 3), each domain ships as its **own
distribution** that imports under a `pirn_<x>` name — it is no longer bundled
inside `pirn`:

| Domain | Distribution (`pip install …`) | Import package | Doc |
|--------|-------------------------------|----------------|-----|
| Data | `pirn-data` | `pirn_data` | [Data](data.md) |
| Agents | `pirn-agents` | `pirn_agents` | [Agents](agents.md) |
| ML | `pirn-ml` | `pirn_ml` | [ML](ml.md) |
| Health | `pirn-health` | `pirn_health` | [Health](health.md) |
| Signal | `pirn-signal` | `pirn_signal` | [Signal](signal.md) |
| Oil & Gas | `pirn-oilgas` | `pirn_oilgas` | [Oil & Gas](oilgas.md) |

Install only the domains you need; each depends on `pirn-core` (the `pirn_ml`
package additionally depends on `pirn_data`, ADR-3). For monolith ergonomics,
the opt-in `pip install 'pirn-core[all-domains]'` aggregate pulls all six at
once — see the [migration guide](../guides/migrating-to-split-packages.md).

## Registry self-registration

Importing a domain package is what **registers its knots** under
`library="pirn"`, so a YAML pipeline can resolve them by bare name (ADR-4). A
plain `import pirn_data` (or any `pirn_<x>`) triggers the package's
`Registry.fill_registry()` on import; nothing else is required. When you build
pipelines in Python you import the knot classes directly, which has the same
effect.

The convenience helper `pirn.discover_installed_domains()` imports **every**
installed `pirn_*` domain package in one call (and returns the import names it
loaded), so a YAML-only deployment can register all available domains up front
without naming each one:

```python
import pirn

pirn.discover_installed_domains()   # imports every installed pirn_<x>
```

## Legacy `pirn.domains.*` paths (deprecated)

The pre-split import paths `pirn.domains.<x>` still resolve for **one
deprecation cycle** via a compatibility shim that defers to the standalone
`pirn_<x>` package and emits a `DeprecationWarning`. Migrate to the
`pirn_<x>` imports — the [migration guide](../guides/migrating-to-split-packages.md)
covers the automated codemod (`pirn-migrate-imports`) and the full mapping.
