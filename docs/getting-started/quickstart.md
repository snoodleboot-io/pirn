# Quickstart

This page walks you from a bare Python environment to a running pirn pipeline, reading the results and querying lineage.

---

## Installation

pirn requires Python 3.11 or later.

```bash
pip install pirn
```

The base install gives you the full API with in-memory backends — no database, no external services needed. For production backends, install the relevant extra:

=== "SQLite"

    ```bash
    pip install pirn[sqlite]
    ```

=== "Postgres"

    ```bash
    pip install pirn[postgres]
    ```

=== "DuckDB"

    ```bash
    pip install pirn[duckdb]
    ```

=== "S3"

    ```bash
    pip install pirn[s3]
    ```

=== "ValKey"

    ```bash
    pip install pirn[valkey]
    ```

=== "OpenTelemetry"

    ```bash
    pip install pirn[otel]
    ```

=== "Everything"

    ```bash
    pip install pirn[all]
    ```

---

## Hello World knot

A knot is the fundamental unit of work in pirn. Use `@knot` to wrap an async function:

```python
from pirn import knot


@knot
async def double(x: int) -> int:  # (1)
    return x * 2
```

1. pirn reads the type hints and validates inputs and outputs at run time. The `-> int` annotation is enforced — returning a string here would produce an `Err`.

Sync functions work too — pirn wraps them with `asyncio.to_thread` automatically:

```python
@knot
def to_upper(text: str) -> str:
    return text.upper()
```

You can also subclass `Knot` directly for richer behaviour:

```python
from pirn import Knot, KnotConfig

class EnrichUser(Knot):
    async def process(self, user_id: str, lookup_table: dict) -> dict:
        return lookup_table.get(user_id, {})
```

---

## Building a tapestry

Knots are wired inside a `Tapestry` context manager. Pass one knot as a kwarg to another to declare a dependency:

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig, knot, RunRequest


@knot
async def double(x: int) -> int:
    return x * 2


@knot
async def add(a: int, b: int) -> int:
    return a + b


with Tapestry() as t:  # (1)
    x = Parameter("x", int)  # (2)
    d = double(
        x=x,                    # (3)
        _config=KnotConfig(id="d"),
    )
    answer = add(
        a=x,                    # (4)
        b=d,
        _config=KnotConfig(id="answer"),
    )
```

1. The `with Tapestry() as t:` block sets a context variable. Every knot constructed inside auto-registers with `t`.
2. `Parameter` declares an external input. Its id is `"x"` and it accepts integers. You provide the value in `RunRequest`.
3. Passing `x` (a knot instance) as a kwarg declares `double` depends on `x`'s output. The kwarg name `x` matches `double.process`'s parameter name.
4. `add` depends on both `x` and `d`. pirn derives the topological execution order automatically.

!!! note "Every knot needs an explicit id"
    pirn does not auto-generate knot ids. Readable ids are necessary for lineage records to be useful across runs. Use `_config=KnotConfig(id="...")` every time.

---

## Running it

`tapestry.run()` is an async method. Call it from an async context:

```python
async def main():
    result = await t.run(RunRequest(parameters={"x": 5}))
    return result

result = asyncio.run(main())
```

`RunRequest` carries the parameter values that bind to `Parameter` knots at run time. Every run gets a unique `run_id`.

---

## Reading results

`RunResult` is a Pydantic model with several useful fields:

```python
# Raw output values for every Ok knot
print(result.outputs)
# {'param:x': 5, 'd': 10, 'answer': 15}

# Did any knot fail?
print(result.succeeded)
# True

# Which knots ran, skipped, or errored?
for record in result.lineage:
    print(record.knot_id, record.outcome, record.started_at)
```

Each `KnotLineage` record carries:

| Field | Description |
|-------|-------------|
| `run_id` | UUID of the run |
| `knot_id` | The `id=` from `KnotConfig` |
| `knot_class` | Fully-qualified class name |
| `outcome` | `"ok"`, `"err"`, or `"skipped"` |
| `output_hash` | `sha256:…` of the output value (Ok only) |
| `parent_input_hashes` | `{name: sha256:…}` for each input |
| `knot_config_hash` | Hash of the knot's config at run time |
| `started_at` / `finished_at` | UTC datetimes |
| `dispatcher` | Which dispatcher ran the knot |

---

## Lineage queries

Because pirn uses content-addressed hashing, you can query across runs:

```python
# What other runs produced this same output value?
out_hash = result.lineage[2].output_hash
matches = await t.history.query_lineage_by_output_hash(out_hash)

# Who consumed this value as input in any run?
consumers = await t.history.query_lineage_by_input_hash(out_hash)

# Full history of a specific knot
history = await t.history.query_lineage_by_knot_id("answer")
for rec in history:
    print(rec.run_id, rec.outcome, rec.output_hash)
```

The lineage graph is maintained regardless of whether you scrub the actual values from the `DataStore`. This lets you implement GDPR-style value erasure without destroying audit history.

---

## Handling errors

Every knot produces one of three results:

- `Ok(value)` — success.
- `Err(record)` — exception was raised; the `record` contains type, message, and traceback.
- `Skipped(reason)` — knot was not run (parent failed, gate closed, branch not selected).

By default, a knot whose parent failed is skipped (`SKIP_IF_PARENT_FAILED`). You can change this per knot:

```python
from pirn import ErrorPolicy

# This knot receives Result objects directly — it handles failures itself
@knot
async def summarise(left: int, right: int) -> str:
    return f"{left} + {right}"

KnotConfig(id="s", error_policy=ErrorPolicy.RECEIVE_ERRORS)
```

See [Error Handling](../guides/error-handling.md) for the full reference.

---

## What next?

- [Concepts](concepts.md) — full glossary of pirn terms
- [First Pipeline](first-pipeline.md) — build a realistic content moderation pipeline
- [Backends](../guides/backends.md) — choose the right storage for production
- [Visualization](../guides/visualization.md) — explore pipeline structure and run history
