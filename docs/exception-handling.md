# Exception Handling and Traceback Safety

This document covers how pirn captures exceptions, how to filter sensitive
data from stored tracebacks, and how to control emitter error behaviour.

---

## ExceptionRecord

Every exception caught during a run is stored as an `ExceptionRecord`:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Run-scoped identifier (e.g. `exc-a1b2c3d4e5f6`). Referenced by `KnotLineage.error_record_id`. |
| `run_id` | `str` | The run this record belongs to. |
| `knot_id` | `str` | The knot that raised the exception. |
| `exc_type` | `str` | `type(exc).__name__` (e.g. `"ValueError"`). |
| `message` | `str` | `str(exc)`. |
| `traceback_text` | `str` | Full formatted traceback from `traceback.format_exception`. |
| `occurred_at` | `datetime` | UTC timestamp of capture. |

Records are frozen Pydantic models — safe to serialise, log, or store.

---

## Configuring a Traceback Filter

Pass `traceback_filter` to `Tapestry` (constructor or `run()`) to sanitise
every `traceback_text` before it is stored:

```python
from pirn import Tapestry, redact_common_secrets

# Apply at construction — all runs use the filter.
t = Tapestry(traceback_filter=redact_common_secrets)

# Or per-run only:
result = await t.run(traceback_filter=redact_common_secrets)
```

The filter is a plain callable `(str) -> str` applied after the traceback
string is assembled but before `ExceptionRecord` is created.

---

## Built-in Filter: `redact_common_secrets`

`pirn.redact_common_secrets` replaces the most common credential patterns
with `<redacted>`.

### Patterns matched

| Pattern | Example before | Example after |
|---------|---------------|---------------|
| DSN credentials | `postgresql://admin:s3cr3t@db:5432/mydb` | `postgresql://<redacted>@db:5432/mydb` |
| Named assignment (`password`, `passwd`, `api_key`, `token`, `secret`, `auth`) | `password=hunter2` | `password=<redacted>` |
| HTTP Authorization header | `Authorization: Bearer eyJhb...` | `Authorization: Bearer <redacted>` |

### Example

```python
from pirn.managers.exceptions import redact_common_secrets

before = (
    "Traceback (most recent call last):\n"
    "  File 'app.py', line 10, in connect\n"
    "    db.connect('postgresql://admin:s3cr3t@prod-db:5432/app')\n"
    "ConnectionError: password=s3cr3t was rejected\n"
)

after = redact_common_secrets(before)
# after contains:
#   postgresql://<redacted>@prod-db:5432/app
#   password=<redacted>
```

---

## Writing a Custom Filter

Any `(str) -> str` callable works:

```python
import re

_MY_TOKEN = re.compile(r'MY_APP_TOKEN=[^\s]+')

def my_filter(text: str) -> str:
    return _MY_TOKEN.sub('MY_APP_TOKEN=<redacted>', text)

t = Tapestry(traceback_filter=my_filter)
```

Filters can be chained:

```python
def combined(text: str) -> str:
    text = redact_common_secrets(text)
    return my_filter(text)
```

---

## Minimising Traceback Exposure (Coding Conventions)

Even with a filter, the best defence is keeping secrets out of tracebacks:

1. **Don't hold secrets in named locals across `await` boundaries.** Python's
   traceback captures local variable names (but not values). Some logging
   frameworks do capture locals — keep secret lifetime short.

2. **Load credentials once at startup, not inline.** Passing a raw credential
   string directly to a function that raises means the string is in the
   exception message and the traceback. Wrap connection setup and catch narrow
   exceptions before they propagate.

3. **Use placeholder knots for secret injection.** Pass secrets via
   `Parameter` knots from a vault at run time; the `Parameter.value` is never
   part of a traceback unless you explicitly include it in a raise.

4. **Prefer structured errors over raw exception propagation.** Catch
   third-party library exceptions early and re-raise with a sanitised message:
   ```python
   except SomeLibraryError as exc:
       raise RuntimeError("connection failed") from None
   ```

---

## EmitterErrorPolicy

`EmitterErrorPolicy` (a `StrEnum`) controls what happens when an emitter
raises during `on_lineage` or `on_run_result`:

| Value | Behaviour |
|-------|-----------|
| `WARN` (default) | Log a `WARNING` and continue. The run result is unaffected. |
| `IGNORE` | Swallow the error silently. Use when emitter failures are expected and unimportant. |
| `RAISE` | Propagate the exception, aborting run finalisation. Use in tests or when emitter correctness is critical. |

### Usage

```python
from pirn import Tapestry, EmitterErrorPolicy

# Constructor default — all runs use WARN.
t = Tapestry(emitter_error_policy=EmitterErrorPolicy.WARN)

# Override per-run.
result = await t.run(emitter_error_policy=EmitterErrorPolicy.RAISE)
```

### When to use each option

- **`WARN`** — Production pipelines where observability emitters (log
  shippers, metrics sinks) should never block a business-critical run.
- **`IGNORE`** — Best-effort emitters (e.g. a Slack notifier) where total
  silence is preferable to log noise.
- **`RAISE`** — Integration tests that assert emitter correctness, or
  development environments where a silent emitter failure would mask bugs.
