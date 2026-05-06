# Error Handling

This guide covers how pirn captures exceptions, how the three-way result type propagates through a pipeline, how to configure per-knot error policies, and how to filter sensitive data from stored tracebacks.

---

## The three-way result

Every knot produces exactly one of:

| Variant | When | Fields |
|---------|------|--------|
| `Ok(value)` | `process()` returned normally | `value: T` — the typed output |
| `Err(record)` | `process()` raised any exception | `record: ExceptionRecord` |
| `Skipped(reason)` | Knot was deliberately not run | `reason: str`, `detail: dict` |

`Skipped` is not the same as `Err`. A skipped knot means "didn't run" — because a parent failed, a gate was closed, or a branch was not selected. Distinguishing skip from crash allows downstream knots and emitters to react appropriately.

```python
result = await tapestry.run(request)

for record in result.lineage:
    if record.outcome == "err":
        print(f"FAILED: {record.knot_id}")
        exc = result.exceptions[record.error_record_id]
        print(exc.exc_type, exc.message)
    elif record.outcome == "skipped":
        print(f"SKIPPED: {record.knot_id} — {record.skip_reason}")
```

---

## Error policies

Set per-knot via `_config=KnotConfig(id="...", error_policy=ErrorPolicy.xxx)`.

### `SKIP_IF_PARENT_FAILED` (default)

If any parent produced `Err` or `Skipped`, this knot becomes `Skipped` without calling `process()`. The skip propagates downstream. Use for most knots that cannot meaningfully proceed without upstream data.

```python
from pirn import KnotConfig, ErrorPolicy

answer = add(
    a=x, b=d,
    _config=KnotConfig(id="answer", error_policy=ErrorPolicy.SKIP_IF_PARENT_FAILED),
)
```

**Chain behaviour:** `A → B → C` where B fails. C is `Skipped` (not `Err`). Any knot downstream of C is also `Skipped`.

### `RECEIVE_ERRORS`

The engine calls `process()` unconditionally, passing `Result` objects as arguments instead of unwrapped values. Use for aggregation, fallback, or circuit-breaker knots.

```python
from pirn import Knot, KnotConfig, ErrorPolicy
from pirn.core.result import Result

class Summarise(Knot):
    async def process(
        self,
        left: Result[int],  # (1)
        right: Result[int],
    ) -> int:
        lv = left.value if left.is_ok else 0
        rv = right.value if right.is_ok else 0
        return lv + rv

    # Configure the policy:
    # Summarise(left=..., right=..., _config=KnotConfig(id="s", error_policy=ErrorPolicy.RECEIVE_ERRORS))
```

1. Declare `process()` parameters as `Result[T]` — pirn passes the raw `Result` object, not the unwrapped value.

### `REQUIRE_ALL_PARENTS`

If any parent produced `Err` or `Skipped`, the engine injects a synthetic `Err` without calling `process()`. This makes failures explicit rather than silently propagating skips. Use when partial inputs are meaningless and a visible failure is preferable.

```python
critical = pipeline_step(
    data=upstream,
    _config=KnotConfig(id="critical", error_policy=ErrorPolicy.REQUIRE_ALL_PARENTS),
)
```

---

## The `Optional` mixin

`Optional` signals that a knot's own failure is tolerable — it should be treated as a `Skipped` for downstream consumers rather than an `Err`.

```python
from pirn import Optional, Knot, KnotConfig

class FetchPrefs(Optional, Knot):
    async def process(self, user_id: str) -> dict:
        return await prefs_api.get(user_id)  # might fail

prefs = FetchPrefs(user_id=uid, _config=KnotConfig(id="prefs"))
```

If `FetchPrefs` raises, its result is converted from `Err` to `Skipped`. Downstream knots with `SKIP_IF_PARENT_FAILED` are then skipped gracefully — no error alarm for an optional enrichment step.

!!! note "Optional does not affect error propagation policy"
    `Optional` changes how the *knot's own outcome* is interpreted, not how it handles parent failures. A child knot's `error_policy` still controls what happens when it sees the Optional knot's `Skipped` output.

---

## ExceptionRecord

Every exception caught during a run is stored as an `ExceptionRecord`:

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Run-scoped identifier, e.g. `exc-a1b2c3d4` |
| `run_id` | str | The run this record belongs to |
| `knot_id` | str | The knot that raised the exception |
| `exc_type` | str | `type(exc).__name__` |
| `message` | str | `str(exc)` |
| `traceback_text` | str | Full formatted traceback |
| `occurred_at` | datetime | UTC timestamp of capture |

Records are frozen Pydantic models — safe to serialise, log, or store.

```python
for record in result.lineage:
    if record.error_record_id:
        exc_rec = result.exceptions[record.error_record_id]
        print(exc_rec.exc_type, exc_rec.message)
        print(exc_rec.traceback_text)
```

---

## Traceback filters

Tracebacks can contain secrets — DSN credentials in error messages, API keys in locals. Pirn lets you apply a filter to every traceback before it is stored.

### Built-in filter: `redact_common_secrets`

```python
from pirn import Tapestry, redact_common_secrets

# Apply to all runs from this tapestry
t = Tapestry(traceback_filter=redact_common_secrets)

# Or override per-run
result = await t.run(request, traceback_filter=redact_common_secrets)
```

`redact_common_secrets` replaces these patterns with `<redacted>`:

| Pattern | Example before | Example after |
|---------|---------------|---------------|
| DSN credentials | `postgresql://admin:s3cr3t@db/app` | `postgresql://<redacted>@db/app` |
| Named assignments | `password=hunter2` | `password=<redacted>` |
| HTTP Authorization | `Authorization: Bearer eyJ…` | `Authorization: Bearer <redacted>` |

### Custom filter

Any `(str) -> str` callable works:

```python
import re

_TOKEN_RE = re.compile(r'MY_APP_TOKEN=[^\s]+')

def my_filter(text: str) -> str:
    return _TOKEN_RE.sub('MY_APP_TOKEN=<redacted>', text)

# Chain filters
def combined(text: str) -> str:
    return my_filter(redact_common_secrets(text))

t = Tapestry(traceback_filter=combined)
```

---

## Emitter error policy

Controls what happens when an emitter raises during `on_lineage` or `on_run_result`:

| Value | Behaviour |
|-------|-----------|
| `WARN` (default) | Log a warning and continue — the run result is unaffected |
| `IGNORE` | Swallow silently — for best-effort emitters |
| `RAISE` | Propagate the exception — for tests that assert emitter correctness |

```python
from pirn import EmitterErrorPolicy

t = Tapestry(emitter_error_policy=EmitterErrorPolicy.RAISE)

# Or per-run
result = await t.run(request, emitter_error_policy=EmitterErrorPolicy.RAISE)
```

---

## Best practices

1. **Keep secrets out of exception messages.** Catch third-party library exceptions early and re-raise with sanitised messages:
   ```python
   try:
       conn = await db.connect(dsn)
   except ConnectionError as exc:
       raise RuntimeError("database connection failed") from None
   ```

2. **Use `Optional` for enrichment knots.** If a knot fetches optional data (preferences, metadata), mix in `Optional` so its failure doesn't cascade.

3. **Use `REQUIRE_ALL_PARENTS` for critical path.** When partial execution would produce misleading outputs, make the failure explicit.

4. **Test your error paths.** Use `InMemoryStore` + `InMemoryHistory` with deliberately failing knots. See [Testing](testing.md) for patterns.

5. **Monitor `Skipped` as well as `Err`.** A flood of unexpected skips can indicate an upstream failure silently propagating.

---

**See also:** [Concepts — Ok / Err / Skipped](../getting-started/concepts.md#ok-err-skipped), [API — Core](../api/core.md)
