# Knot Registration

Pirn looks knots up by name through `sweet_tea`'s registry. Anywhere you want a Knot to be referenced by name — YAML pipelines, dynamic dispatch, the explorer, your own factory code — that knot must be registered. This page is the single source of truth for *how* registration happens, *what you must do* in your own project, and *what the alternatives are* if you can't use auto-discovery.

---

## The model in one paragraph

Pirn calls `sweet_tea.registry.Registry.fill_registry()` over its own package tree at import time. Every `Knot` subclass that ships with pirn is auto-registered under `library="pirn"` with the snake-case form of its class name as the key. Lookup goes through `sweet_tea.abstract_inverter_factory.AbstractInverterFactory[Knot]`, which returns the class definition (the loader instantiates it later with the right kwargs). Sweet_tea's `BaseFactory._generate_key_variations` handles `CamelCase`, `snake_case`, and `nounderscores` forms — all three resolve to the same entry.

**For your own knots, you must call** `Registry.fill_registry()` **from your own project's package init.** Pirn only auto-discovers its own tree.

---

## Recommended: auto-discovery via `fill_registry`

Put one line in your project's top-level `__init__.py`:

```python
# my_company/__init__.py
from sweet_tea.registry import Registry

Registry.fill_registry()   # scans my_company/ recursively, registers every class defined here
```

After that, every `Knot` subclass anywhere under `my_company/` is resolvable by name. No manual list to maintain, no import-order traps, no boilerplate at every callsite.

Two important properties:

- **It only registers classes defined in *your* package.** Classes you import from third parties don't get re-registered under your library — `fill_registry` checks `obj.__module__` against the module currently being scanned.
- **Optional dependencies are skipped gracefully.** A submodule that fails to import because an optional extra isn't installed emits a `SweetTeaWarning` and is skipped — the rest of your registry still populates.

YAML usage after that:

```yaml
nodes:
  - id: extract
    callable: object_store_read_source     # pirn-shipped knot
  - id: clean
    callable: normalise_addresses          # your knot
    parents: [extract]
```

```python
tapestry = load_pipeline(yaml_text)        # no known_callables= needed
```

---

## Manual registration: when you can't (or don't want to) use auto-discovery

There are three reasons you might want manual registration instead of (or in addition to) `fill_registry`:

1. **Aliasing.** You want the same class registered under more than one name (e.g. a short alias for YAML readability).
2. **`@knot`-decorated functions.** The `@knot` decorator returns a `KnotFactory`, not a `Knot` subclass — `fill_registry` does register the underlying class, but if you want a custom name you'll register the factory's `.knot_class` explicitly.
3. **Dynamic registration.** A class only known at runtime (loaded from a plugin manifest, configured at startup, etc.).

### One class

```python
from sweet_tea.registry import Registry
from my_company.knots.normalise_addresses import NormaliseAddresses

Registry.register(
    "normalise_addresses",     # registry key (lowercased on store)
    NormaliseAddresses,        # the class itself
    library="my_company",      # so users can scope lookups by library
)
```

### A `@knot`-decorated factory

```python
from sweet_tea.registry import Registry
from my_company.knots import score_text

Registry.register(
    "score_text",
    score_text.knot_class,     # the underlying Knot subclass
    library="my_company",
)
```

### Many classes from a list

```python
from sweet_tea.registry import Registry
from my_company.knots import (
    NormaliseAddresses, MatchHouseholds, AppendDemographics,
)

for cls in (NormaliseAddresses, MatchHouseholds, AppendDemographics):
    Registry.register(cls.__name__.lower(), cls, library="my_company")
```

---

## Direct lookup (when you want the class, not an instance)

The YAML loader already does this internally; you only need it if you're writing your own factory code:

```python
from sweet_tea.abstract_inverter_factory import AbstractInverterFactory
from pirn.core.knot import Knot

knot_class = AbstractInverterFactory[Knot].create("normalise_addresses")
instance   = knot_class(input=..., _config=KnotConfig(id="..."))
```

To scope to a specific library:

```python
knot_class = AbstractInverterFactory[Knot].create(
    "normalise_addresses",
    library="my_company",
)
```

A missing key, an ambiguous match, or a wrong library raises `sweet_tea.sweet_tea_error.SweetTeaError`.

---

## Lifecycle: when does registration need to be done?

Registration must complete **before** any factory query that touches the same parent type. In practice this means:

- Pirn's own knots are registered at import time of the `pirn` package.
- Your project's knots should be registered at import time of *your* package — keep `Registry.fill_registry()` at module top in your `__init__.py` and import your package before you load any YAML or call any factory.
- Don't interleave `register()` calls with `AbstractInverterFactory.create()` calls in the same lifecycle — register everything first, query afterwards.

If you can't follow that ordering for some reason (rare — usually only in tests), be aware that `sweet_tea.registry.Registry.typed_entries` caches its filtered results per lookup type and is not refreshed when later `register()` calls add new subclasses of an already-cached parent type. Treat registration as a startup phase, not an ongoing one.

---

## Troubleshooting

**`callable: my_knot` resolves to a `ValueError` saying "not in known_callables and not registered as a Knot"**
You forgot to call `Registry.fill_registry()` from your project's `__init__.py`, or the module containing `my_knot` was skipped because an optional dependency is missing.  Check for `SweetTeaWarning` messages at startup.

**`SweetTeaError: The combination of key X, label, and library did not return a unique result`**
Two classes are registered under the same key. Use `library="..."` to disambiguate, or rename one.

**`SweetTeaError: The key X not present`**
The class was never registered, or registration happened in a module that wasn't imported by the time the lookup ran. Make sure your package's `__init__.py` runs before any YAML load.

**A class is registered (you can see it in `Registry.entries()`) but `AbstractInverterFactory[Knot].create(...)` doesn't find it**
You probably called a factory query *before* registering the class, in a process where sweet_tea's typed-lookup cache was already populated for `Knot`. Restart the process and put all registrations before any queries; if you genuinely need register-then-query ordering, file an issue against sweet_tea.

---

## Quick reference

| Task | API |
|------|-----|
| Auto-register everything in your project | `Registry.fill_registry()` from your project `__init__.py` |
| Register one class | `Registry.register(key, cls, library="...")` |
| Register a `@knot`-decorated factory | `Registry.register(key, factory.knot_class, library="...")` |
| Look up a class by name | `AbstractInverterFactory[Knot].create(key)` |
| Look up scoped to a library | `AbstractInverterFactory[Knot].create(key, library="...")` |
| Iterate all registered Knots | `Registry.typed_entries(lookup_type=Knot)` |
| Iterate everything in the registry | `Registry.entries()` |

---

**See also:** [YAML Pipelines](yaml-pipelines.md) for how the loader uses these APIs; [Concepts](../getting-started/concepts.md) for the surrounding pirn vocabulary.
