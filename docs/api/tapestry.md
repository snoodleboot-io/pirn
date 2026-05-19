# Tapestry

The `Tapestry` is the central workspace. Build knots inside a `with Tapestry() as t:` block to auto-register them, then call `t.run(request)` to execute the pipeline.

---

## Quick reference

```python
from pirn import Tapestry, RunRequest, Parameter, KnotConfig, knot

@knot
async def double(x: int) -> int:
    return x * 2

with Tapestry() as t:
    x = Parameter("x", int)
    d = double(x=x, _config=KnotConfig(id="d"))

result = await t.run(RunRequest(parameters={"x": 5}))
# result.outputs → {"param:x": 5, "d": 10}
```

---

## API reference

::: pirn.tapestry.Tapestry
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## Identity resolution

pirn auto-resolves WHO initiated each run. The default resolver checks CI env vars first (`GITHUB_ACTOR`, `GITLAB_USER_LOGIN`, `CI_USER`, `BUILD_USER`), then falls back to the OS user. Every run result carries the resolved `actor` and an optional `trigger`.

```python
from pirn import Tapestry, RunRequest
from pirn.core.identity import StaticIdentityResolver, NullIdentityResolver

# Production service — fixed service account
tapestry = Tapestry(identity_resolver=StaticIdentityResolver("svc-ingest"))

# Explicit actor on a single run — overrides any resolver
result = await tapestry.run(RunRequest(actor="alice@example.com", trigger="webhook:order-placed"))
print(result.actor)    # "alice@example.com"
print(result.trigger)  # "webhook:order-placed"

# Tests — suppress resolution entirely
tapestry = Tapestry(identity_resolver=NullIdentityResolver())
```

All resolver classes live in `pirn.core.identity`:

| Class | Behaviour |
|---|---|
| `OsIdentityResolver` | `getpass.getuser()` — default fallback |
| `EnvIdentityResolver(vars)` | First non-empty value from env var list |
| `StaticIdentityResolver(actor)` | Fixed string — for services and CI jobs |
| `ChainedIdentityResolver(resolvers)` | First non-None result from a list of resolvers |
| `NullIdentityResolver` | Always `None` — use in tests to suppress resolution |

The default resolver is `ChainedIdentityResolver([EnvIdentityResolver(), OsIdentityResolver()])`.

---

## get_current_store

```python
from pirn.tapestry import get_current_store
```

Returns the `TapestryStore` of the currently-executing extensible run, or `None` when called outside an extensible run.

Call this inside a knot's `process()` to register successor knots into the running tapestry. The engine picks them up between waves — this is the mechanism for building dynamic DAGs where the graph structure is determined by runtime output.

```python
from pirn.tapestry import get_current_store
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

class RouterKnot(Knot):
    async def process(self, result: dict, **_) -> dict:
        store = get_current_store()
        if store is not None:
            if result["needs_enrichment"]:
                store.register(EnrichKnot(data=self, _config=KnotConfig(id="enrich")))
            else:
                store.register(FinaliseKnot(data=self, _config=KnotConfig(id="finalise")))
        return result
```

Requires `extensible=True` on the enclosing `tapestry.run()` call. In a non-extensible run this always returns `None` and registered knots are silently dropped.
