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
