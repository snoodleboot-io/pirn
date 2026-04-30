# Fan-Out with Map

The `Map` node applies an inner knot to each element of a collection-producing parent. It is the primary way to fan out over dynamic lists in pirn.

---

## Basic fan-out

Suppose you have a knot that produces a list of IDs, and you want to enrich each one independently:

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig, knot, RunRequest, Map


@knot
async def fetch_ids(category: str) -> list[str]:
    """Fetch a list of record IDs for the given category."""
    # In production this would query a database.
    return [f"{category}-001", f"{category}-002", f"{category}-003"]


@knot
async def enrich_record(record_id: str) -> dict:
    """Fetch details for a single record."""
    return {"id": record_id, "score": len(record_id) * 0.1, "status": "active"}


async def main():
    with Tapestry() as t:
        category = Parameter("category", str)

        ids = fetch_ids(
            category=category,
            _config=KnotConfig(id="ids"),
        )

        enriched = Map(
            over=ids,                # (1) parent that produces the list
            each=enrich_record,      # (2) knot applied to each element
            bind="record_id",        # (3) parameter name in enrich_record.process()
            _config=KnotConfig(id="enriched"),
        )

    result = await t.run(RunRequest(parameters={"category": "widget"}))
    print(result.outputs["enriched"])
    # [{"id": "widget-001", ...}, {"id": "widget-002", ...}, {"id": "widget-003", ...}]


asyncio.run(main())
```

1. `over=ids` — the parent knot that produces `list[str]`.
2. `each=enrich_record` — the knot (or `@knot` function) applied to each element.
3. `bind="record_id"` — the parameter name in `enrich_record.process()` that receives each element.

---

## Fan-out with shared config

Pass static values shared across all element calls using `shared`:

```python
@knot
async def score_text(text: str, model: str) -> float:
    return 0.5  # placeholder


with Tapestry() as t:
    texts_param = Parameter("texts", list)
    scored = Map(
        over=texts_param,
        each=score_text,
        bind="text",
        shared={"model": "v2"},    # passed to every score_text call
        _config=KnotConfig(id="scored"),
    )
```

---

## Chaining Map with Reduce

After fanning out with `Map`, use `Reduce` to fold the results back into a single value:

```python
from pirn import Reduce


@knot
async def fetch_item_ids(batch: str) -> list[str]:
    return ["a", "b", "c"]


@knot
async def compute_cost(item_id: str) -> float:
    return {"a": 1.0, "b": 2.5, "c": 0.75}[item_id]


async def main():
    with Tapestry() as t:
        batch = Parameter("batch", str)

        ids = fetch_item_ids(
            batch=batch,
            _config=KnotConfig(id="ids"),
        )

        costs = Map(
            over=ids,
            each=compute_cost,
            bind="item_id",
            _config=KnotConfig(id="costs"),
        )

        total = Reduce(
            of=costs,
            combine=sum,              # whole-list combine: sum([1.0, 2.5, 0.75])
            _config=KnotConfig(id="total"),
        )

    result = await t.run(RunRequest(parameters={"batch": "order-99"}))
    print(f"Total cost: {result.outputs['total']}")
    # Total cost: 4.25


asyncio.run(main())
```

---

## Pairwise reduce

For large lists where the combine function is associative, use pairwise reduce with an initial value:

```python
total = Reduce(
    of=costs,
    combine=lambda a, b: a + b,   # pairwise: called as (acc, item) repeatedly
    initial=0.0,
    _config=KnotConfig(id="total"),
)
```

---

## Fan-out in YAML

```yaml
name: fan_out_example

nodes:
  - id: category
    type: parameter
    type_: str

  - id: ids
    type: knot
    callable: fetch_ids
    parents:
      category: category

  - id: enriched
    type: map
    over: ids
    each: enrich_record
    bind: record_id

  - id: total_count
    type: reduce
    of: enriched
    combine: count_records    # callable: (list) -> int
```

---

## Lineage for Map output

Each element processed by `Map` is captured in the lineage. The `Map` knot's `output_hash` covers the entire output list, content-addressed. Individual element results are not stored separately — the whole list is the unit of lineage.

```python
lineage = {rec.knot_id: rec for rec in result.lineage}
print(lineage["enriched"].output_hash)   # sha256:… of the entire list
print(lineage["enriched"].outcome)       # "ok"
```

---

**See also:** [Nodes — Map](../api/nodes.md#map), [Nodes — Reduce](../api/nodes.md#reduce), [Concepts](../getting-started/concepts.md)
