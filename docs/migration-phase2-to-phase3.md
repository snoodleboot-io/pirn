# Migrating from Phase 2 to Phase 3

**Short version: nothing to do.** The Phase 3 API is fully additive.
Existing Phase 2 code runs unchanged; new features are opt-in.

---

## What changed

### Default backends are unchanged

Phase 2 code that constructs `Tapestry()` with no arguments still gets
`InMemoryStore` + `InMemoryHistory` + `InMemoryDataStore`. There is no
implicit migration of stored data and no new required parameters.

```python
# Phase 2 — still works exactly as before
t = Tapestry()
result = await t.run(RunRequest(parameters={"x": 1}))
```

### New `emitters=` parameter on `Tapestry`

Phase 3 adds an optional `emitters` list to the `Tapestry` constructor and
to `Tapestry.run()`. If you don't pass it, behaviour is identical to Phase 2
(no emitters, no side effects).

```python
# Phase 2 style — unchanged
t = Tapestry(store=my_store, history=my_history)

# Phase 3 — add emitters when you're ready
from pirn.emitters import LogEmitter, OpenTelemetryEmitter
t = Tapestry(store=my_store, history=my_history,
             emitters=[LogEmitter(), OpenTelemetryEmitter()])
```

You can also override emitters for a single run without changing the
tapestry's defaults:

```python
result = await t.run(request, emitters=[])          # disable for this run
result = await t.run(request, emitters=[my_emitter]) # override for this run
```

### New `extensible=` parameter on `Tapestry.run`

`run()` now accepts `extensible=True` to enable mid-run extension (adding
knots while a run is in progress). This requires a `SubscribableStore`
backend (`InMemoryStore` supports it; SQLite/Postgres/ValKey do too via
LISTEN/NOTIFY or pub/sub). The default is `extensible=False` — no change
to existing call sites.

```python
# Phase 3 only — opt in explicitly
result = await t.run(request, extensible=True)
```

### New optional extras in `pyproject.toml`

Phase 3 adds pip extras for optional backends and integrations. These
install nothing by default; existing installations are not affected.

| Extra | Installs | Use for |
|-------|----------|---------|
| `pirn[sqlite]` | `aiosqlite` | Durable single-host persistence |
| `pirn[postgres]` | `asyncpg` | Multi-host durable persistence |
| `pirn[duckdb]` | `duckdb` | OLAP lineage queries |
| `pirn[valkey]` | `valkey-glide` | Distributed cache + pub/sub |
| `pirn[s3]` | `aioboto3` | Object storage for large intermediates |
| `pirn[otel]` | `opentelemetry-sdk` | Distributed tracing |
| `pirn[kafka]` | `aiokafka` | Event streaming emitter |
| `pirn[dask]` | `dask[distributed]` | Dask dispatcher |
| `pirn[ray]` | `ray` | Ray dispatcher |
| `pirn[celery]` | `celery` | Celery dispatcher |
| `pirn[all]` | everything above | CI / full installs |

Installing any extra does not change runtime behaviour unless you explicitly
construct the corresponding backend class.

---

## Step-by-step upgrade

1. **Upgrade the package.** No code changes required.

   ```bash
   pip install --upgrade pirn
   ```

2. **Run your existing tests.** Everything should pass as-is.

3. **Opt in to durable backends** when you're ready (see
   `docs/choosing-backends.md` for which combination suits your deployment).

   ```bash
   pip install pirn[postgres]
   ```

   ```python
   from pirn.backends.postgres import PostgresStore, PostgresHistory
   t = Tapestry(store=PostgresStore(dsn="…"), history=PostgresHistory(dsn="…"))
   ```

4. **Add emitters** for observability when you want them (see
   `docs/observability.md`).

   ```bash
   pip install pirn[otel]
   ```

   ```python
   from pirn.emitters import OpenTelemetryEmitter
   t = Tapestry(emitters=[OpenTelemetryEmitter()])
   ```

---

## Nothing else to do

There are no breaking changes, no renamed symbols, no removed defaults.
Phase 2 tapestries, knots, `RunRequest`, `KnotConfig`, `Parameter`, and
`RunResult` are all unchanged. The new backends implement the same
`TapestryStore` / `RunHistory` / `DataStore` protocols, so they slot in
as drop-in replacements.
