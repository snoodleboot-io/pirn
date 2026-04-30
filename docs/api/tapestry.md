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
