# pirn Phase 3 follow-up plan

This document enumerates everything remaining after the Phase 3 build. Items
are grouped by priority. Each item is concrete enough to be picked up in a
fresh session: which files to create/edit, what the code should look like,
what "done" means.

Current state at the time of writing:

- 330 tests passing; ruff clean; pyright clean.
- All six Phase 3 tiers structurally implemented.
- Real backends (Postgres, ValKey, Kafka, S3, Dask, Ray, Celery) tested only
  via mock drivers in this repo.
- `docs/real-backend-testing-plan.md` describes the infrastructure but the
  files aren't yet created.

---

## Priority 1 — Real-backend test infrastructure

These items turn the mock-only suite into one that can run against actual
services. They're the highest-value next step because they exercise code
paths the mocks can't.

### 1.1 — `docker-compose.test.yml` at repo root

**Why:** local dev workflow. Contributors should be able to bring up all
backends with one command.

**What:** create `/docker-compose.test.yml` with the exact content from
`docs/real-backend-testing-plan.md` (Postgres 16, ValKey 8, Redpanda for
Kafka, MinIO for S3). Verify each service comes up with `docker compose
-f docker-compose.test.yml up -d` followed by a healthcheck loop.

**Acceptance:** running `docker compose -f docker-compose.test.yml up -d &&
docker compose -f docker-compose.test.yml ps` shows all four services
healthy within 30 seconds. `docker compose -f docker-compose.test.yml down -v`
cleans up.

**Bonus:** add `make test-up` / `make test-down` Makefile targets.

### 1.2 — `tests/integration/test_postgres_real.py`

**Why:** verify Postgres backend against real schema, contention, persistence.

**What:** mirror the test list in `tests/integration/test_postgres_mock.py`,
swapping the fake pool for a real `asyncpg` pool. Use this fixture pattern:

```python
import os
import pytest

pytestmark = pytest.mark.needs_postgres


@pytest.fixture
async def pg_pool():
    dsn = os.environ.get("PIRN_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PIRN_TEST_POSTGRES_URL not set")
    import asyncpg
    pool = await asyncpg.create_pool(dsn)
    # Clean schema before each test.
    async with pool.acquire() as conn:
        await conn.execute("""
            DROP TABLE IF EXISTS lineage_inputs CASCADE;
            DROP TABLE IF EXISTS lineage CASCADE;
            DROP TABLE IF EXISTS runs CASCADE;
            DROP TABLE IF EXISTS knots CASCADE;
        """)
    yield pool
    await pool.close()
```

**Tests to add (one for one with mock except where noted):**

- `test_postgres_history_record_run_and_get_round_trips` — write a real run,
  read it back, verify `RunResult` round-trips through JSONB.
- `test_postgres_history_query_by_output_hash_finds_duplicates` — two runs
  same input, query returns both records.
- `test_postgres_history_query_by_input_hash_uses_join` — verify the JOIN
  actually executes on real Postgres (catches indexing/SQL errors).
- `test_postgres_history_query_by_knot_id` — same.
- `test_postgres_history_concurrent_writes` — **new, mocks can't catch this.**
  Spawn 100 `record_run` calls in parallel via `asyncio.gather`, verify all
  succeed and final row count is correct. Catches missing transactions or
  primary-key contention.
- `test_postgres_history_persistence_across_connections` — **new.** Write
  with one pool, close it, open a new pool with the same DSN, read the data
  back. Catches missing `commit` calls.
- `test_postgres_store_register_round_trips` — verify `PostgresStore`
  registration writes the knot row, query it back via SQL.
- `test_postgres_store_register_handles_id_conflict_with_upsert` — register
  the same id twice with the same instance (idempotent), then with a different
  instance (raises ValueError).

**Acceptance:** with `PIRN_TEST_POSTGRES_URL` set, `pytest -m needs_postgres`
runs all of the above and all pass. With it unset, they skip silently.

### 1.3 — `tests/integration/test_valkey_real.py`

**Why:** verify ValKey backend against a real server.

**What:** mirror `test_valkey_mock.py` against a real `valkey-glide` client.
Fixture pattern:

```python
@pytest.fixture
async def valkey_client():
    url = os.environ.get("PIRN_TEST_VALKEY_URL")
    if not url:
        pytest.skip("PIRN_TEST_VALKEY_URL not set")
    from glide import GlideClient, GlideClientConfiguration, NodeAddress
    # Parse url to host/port.
    config = GlideClientConfiguration([NodeAddress(host="localhost", port=6379)])
    client = await GlideClient.create(config)
    # Flush keys with our test prefix only — don't FLUSHALL on a shared
    # instance.
    keys = await client.keys("pirn:*")
    if keys:
        await client.delete(keys)
    yield client
    await client.close()
```

**Tests to add:**

- All from `test_valkey_mock.py`, executed against a real client.
- `test_valkey_data_store_ttl_actually_expires` — **new.** Set a value with
  `ttl_seconds=1`, sleep 2 seconds, verify `has` returns False. Mocks can't
  test this.
- `test_valkey_data_store_concurrent_put_get` — **new.** 100 parallel puts
  followed by 100 gets, verify all values round-trip.

**Acceptance:** with `PIRN_TEST_VALKEY_URL` set, `pytest -m needs_valkey`
passes.

### 1.4 — `tests/integration/test_kafka_real.py`

**Why:** verify `KafkaTrigger`, `KafkaEmitter`, `KafkaStreamingSource` end-to-end.

**What:** use `aiokafka` to drive real Kafka producers/consumers.

**Critical detail:** Kafka consumer groups are persistent. Each test must use
a unique `group_id` (e.g., `f"pirn-test-{uuid.uuid4()}"`) to avoid offset
state leaking between test runs. Likewise unique topic names per test, or use
a single topic and rely on the consumer-group offset to skip already-consumed
messages.

**Tests to add:**

- `test_kafka_trigger_consumes_real_messages` — produce 3 messages to a
  topic, verify the trigger yields 3 RunRequests with the right parameters.
- `test_kafka_emitter_publishes_to_real_topic` — emit a status event, then
  consume from the same topic and verify the JSON matches.
- `test_kafka_streaming_source_drives_run_per_message` — wire a streaming
  source through `run_stream` against a real Kafka, produce 5 messages,
  verify 5 runs complete with correct outputs.

**Acceptance:** with `PIRN_TEST_KAFKA_URL` set, all three pass.

### 1.5 — `tests/integration/test_s3_real.py`

**Why:** verify S3 DataStore against MinIO (or real AWS S3).

**What:** parallel to `test_s3_mock.py` but against a real bucket. Fixture
creates a unique key prefix per test (`f"pirn-test-{uuid.uuid4()}/"`) so
parallel test runs don't collide.

**Tests to add:**

- All from `test_s3_mock.py`, against a real S3 endpoint.
- `test_s3_data_store_large_value` — **new.** Put a 10MB pickled value,
  verify it round-trips. Mocks store dicts; real S3 has multipart-upload
  thresholds that this exercises.
- `test_s3_data_store_handles_eventual_consistency` — **new.** Put then
  immediately get; while real S3 is now strongly consistent, this guards
  against any latent assumptions.

**Env vars needed:**
```
PIRN_TEST_S3_ENDPOINT=http://localhost:9000  # MinIO
PIRN_TEST_S3_ACCESS_KEY=pirn
PIRN_TEST_S3_SECRET_KEY=pirntestpassword
PIRN_TEST_S3_BUCKET=pirn-test
PIRN_TEST_S3_REGION=us-east-1
```

The `S3DataStore` constructor needs a small change to accept an
`endpoint_url=` parameter; pass it through to `session.client(...)`.

**Acceptance:** `pytest -m needs_s3` passes against MinIO.

### 1.6 — `tests/integration/test_dask_real.py` / `test_ray_real.py` / `test_celery_real.py`

**Why:** verify the distributed dispatchers against real schedulers.

**Dask:** spin up a `LocalCluster` per test (or per session via fixture).
This is fast and doesn't need Docker.

```python
@pytest.fixture(scope="session")
async def dask_client():
    pytest.importorskip("dask.distributed")
    from dask.distributed import Client, LocalCluster
    cluster = LocalCluster(n_workers=2, threads_per_worker=1, processes=True)
    client = await Client(cluster, asynchronous=True)
    yield client
    await client.close()
    cluster.close()
```

**Ray:** `ray.init(local_mode=False)` per session. Note Ray's heavy startup
cost — keep tests minimal.

**Celery:** needs a broker (Redis or RabbitMQ) plus a worker process. The
worker has to import `pirn` and call `register_celery_worker_task(app)`.
Easiest: spawn the worker as a subprocess in a fixture, kill it on teardown.
This is the most fiddly of the three.

**Tests:** for each, the same minimal scenario — submit a knot via the
dispatcher, verify the result is a correct `Ok(...)`. One end-to-end pipeline
test that runs through the engine using each dispatcher.

**Acceptance:** these tests run in CI when the optional extras are installed.

### 1.7 — `.github/workflows/real-backends.yml`

**Why:** continuous verification.

**What:** the YAML in `docs/real-backend-testing-plan.md` is ready to drop
in. Note GitHub Actions service-container quirks (no `command:` overrides; if
Redpanda needs custom flags, switch to running it via `docker run` in a
step).

**Acceptance:** PR-driven; on every PR, the real-backends workflow runs and
must pass before merge. Job time should stay under ~5 minutes total.

### 1.8 — `S3DataStore` needs an `endpoint_url` parameter

**Why:** MinIO and LocalStack require an explicit endpoint. Currently
`S3DataStore` only takes `region`; without `endpoint_url`, aioboto3 hits real
AWS, which fails in tests.

**What:** add to `pirn/backends/s3.py`:

```python
def __init__(
    self,
    *,
    bucket: str,
    prefix: str = "pirn/data/",
    region: str | None = None,
    endpoint_url: str | None = None,  # NEW
    session: Any = None,
) -> None:
    ...
    self._endpoint_url = endpoint_url

# Then in every session.client(...) call:
async with session.client(
    "s3",
    region_name=self._region,
    endpoint_url=self._endpoint_url,
) as s3:
    ...
```

Update `test_s3_mock.py` if it asserts on `client(...)` args.

**Acceptance:** `S3DataStore(bucket="b", endpoint_url="http://localhost:9000")`
works against MinIO.

---

## Priority 2 — Subscribable distributed stores

For mid-run extension to work on real distributed deployments, at least one
of `PostgresStore` and `ValKeyStore` needs to implement `SubscribableStore`.

### 2.1 — `PostgresStore` LISTEN/NOTIFY support

**Why:** mid-run extension on Postgres-backed deployments.

**What:** Postgres has built-in pubsub via `LISTEN` / `NOTIFY`. Add to
`pirn/backends/postgres.py`:

- In `aregister`: after the INSERT, `await conn.execute("NOTIFY pirn_knots,
  $1", knot.knot_id)`.
- New methods on `PostgresStore`:
  ```python
  def subscribe(self, callback: Callable[[Knot], None]) -> object:
      # Spawn a background task that holds a connection in LISTEN mode
      # and dispatches to callback(knot) when notifications arrive.
      # Return a token (could be the task itself).

  def unsubscribe(self, token: object) -> None:
      # Cancel the background task.
  ```

The wrinkle: the callback needs the *live `Knot` instance*, but `NOTIFY`
only carries the id. The subscriber has to look up the live knot — which
means the live cache (`self._live`) is the source of truth, and the NOTIFY
just serves as a "wake up and check the cache" signal.

For cross-process mid-run extension, the live knot doesn't exist on the other
process — only the database snapshot does. Decide: do we want cross-process
mid-run extension at all? If yes, the subscriber needs to deserialize the
knot from the database row, which means the knot class has to be loadable
from its module path. (This is a meaningful design decision; flag it.)

**Tests:** add `test_postgres_store_subscribe_fires_on_notify` to
`test_postgres_real.py`. Verify subscribe/unsubscribe lifecycle, callback
exception isolation, multiple subscribers.

**Acceptance:** `extensible=True` works with a `PostgresStore`.

### 2.2 — `ValKeyStore` pubsub support

**Why:** same as 2.1 for ValKey-backed deployments.

**What:** ValKey has pubsub via `PUBLISH` / `SUBSCRIBE`. Pattern:

- In `aregister`: after the `hset`, `await client.publish("pirn:tapestry:registrations", knot.knot_id)`.
- A second `GlideClient` configured with `pubsub_subscriptions` for the
  registrations channel. Background task pulls messages and dispatches to
  callbacks.

Same cross-process consideration as 2.1.

**Tests:** parallel suite in `test_valkey_real.py`.

**Acceptance:** `extensible=True` works with `ValKeyStore`.

### 2.3 — Cross-process knot reconstruction (decision point)

**Why:** if subscribers in process B need to reconstruct a live knot
registered in process A, they need to load the class from its module path
and rebuild the instance from the stored config + parents JSON. This is
only sometimes possible (depends on the user's package layout).

**Decision needed:** support cross-process mid-run extension or not?

- **If yes:** add `Knot.from_snapshot(class_path, config, parents)` factory
  that imports the class and rebuilds. Document the constraints (knot class
  must be importable in subscriber process; config must round-trip through
  Pydantic JSON).
- **If no:** scope mid-run extension to "same-process subscribers only" and
  document that Postgres/ValKey subscribers fire only when the
  registration happens in the same process.

Recommendation: start with "no" (same-process only), revisit if a real use
case emerges. Document the limitation in `pirn/triggers/base.py` near the
`extensible=` flag.

---

## Priority 3 — Schema migrations

Currently `_ensure_init` runs `CREATE TABLE IF NOT EXISTS`. Production
deployments need versioned migrations.

### 3.1 — Schema version table

**What:** add a `pirn_schema_version` table to each backend's DDL with one
row holding the current version. On `_ensure_init`, compare against the
backend's expected version and run migrations forward.

For Postgres / SQLite:
```sql
CREATE TABLE IF NOT EXISTS pirn_schema_version (version INTEGER PRIMARY KEY);
```

Backend code:
```python
EXPECTED_VERSION = 1

async def _ensure_init(self):
    if self._initialized:
        return
    pool = await self._pool.get()
    async with pool.acquire() as conn:
        # Try to read current version.
        try:
            row = await conn.fetchrow(
                "SELECT version FROM pirn_schema_version"
            )
            current = row["version"] if row else 0
        except asyncpg.UndefinedTableError:
            current = 0
        # Apply migrations.
        for v in range(current, self.EXPECTED_VERSION):
            await self._migrate(conn, from_v=v)
        await conn.execute(
            "INSERT INTO pirn_schema_version (version) VALUES ($1) "
            "ON CONFLICT (version) DO NOTHING",
            self.EXPECTED_VERSION,
        )
    self._initialized = True
```

Each migration is a method `_migrate_0_to_1`, `_migrate_1_to_2`, etc.

**Acceptance:**

- Bring up an old version of the schema, point a new pirn at it, verify the
  schema is upgraded automatically and old data is preserved.
- Two pirn versions run concurrently: the newer one upgrades; the older one
  keeps reading. (This is the harder property — requires forward-compatible
  schema changes only, no destructive renames.)

### 3.2 — Document the migration policy

**Where:** new file `docs/schema-migrations.md`.

**Content:** what changes are allowed without a new version (additive
columns, new indexes, new tables), what requires a new version (renames,
removals, type changes), how to write a backwards-compatible migration.

---

## Priority 4 — Performance and load testing

The current suite proves correctness; nothing proves throughput.

### 4.1 — `tests/perf/` directory with benchmark tests

**What:** add `pytest-benchmark` to dev deps. Write benchmarks for:

- Wave-loop throughput: a 1000-knot tapestry with no real work, measure
  total run time. Target: dominated by Python overhead, not framework code.
- Lineage write rate: 10000 lineage records into Postgres, measure inserts
  per second. Identifies whether the per-record INSERT loop should be
  batched into one COPY.
- Hashing overhead: hash 1MB / 10MB / 100MB of bytes via `content_hash`,
  identify any unnecessary copying.
- Status-event fanout: 100 emitters, 1000 status events, measure dispatch
  overhead. Identifies whether the `loop.create_task` per event is a
  bottleneck.

**Acceptance:** baseline numbers documented in `docs/perf-baseline.md`.
Future regressions detectable via `pytest-benchmark` comparison.

### 4.2 — `record_run` batching for lineage

**Likely finding from 4.1:** writing N lineage records as N separate
INSERTs is slow. Switch to:
- Postgres: `COPY` or `INSERT ... VALUES (...), (...), (...)` with N
  placeholders.
- SQLite: `executemany`.

**Where:** `pirn/backends/postgres.py:PostgresHistory.record_run` and
`pirn/backends/sqlite.py:SQLiteHistory.record_run`.

**Acceptance:** 10x improvement on the lineage-write benchmark, no behavior
change.

### 4.3 — Connection pool sizing

**What:** today the Postgres / ValKey lazy clients use defaults. Document
recommended pool sizes in `docs/deployment-sizing.md` or similar. For
Postgres: `min_size=10, max_size=50` is a starting point for typical async
workloads.

---

## Priority 5 — Docs and examples

### 5.1 — `examples/` directory with realistic deployments

**Why:** the README shows snippets; new users want a working repo to copy.

**What:** create `examples/` with subdirectories:

- `examples/web-pipeline/` — `WebhookTrigger` → tapestry → `LogEmitter`,
  with a `uvicorn` runner script. README explaining how to POST to it.
- `examples/kafka-streaming/` — `KafkaStreamingSource` → tapestry →
  `KafkaEmitter`, with a docker-compose for Kafka and a producer script.
- `examples/postgres-pipeline/` — `PostgresStore` + `PostgresHistory` +
  `S3DataStore`, showing the durable-deployment shape.
- `examples/cron-batch/` — `CronTrigger` running a daily job, with
  `OpenTelemetryEmitter` for traces.

Each example is self-contained: its own `pyproject.toml` (or a shared
parent), runnable, with a README explaining what it demonstrates.

**Acceptance:** `cd examples/web-pipeline && pip install -e . && python
run.py` works end-to-end.

### 5.2 — Backend selection guide

**Where:** new file `docs/choosing-backends.md`.

**Content:** decision matrix — given your deployment shape (single host vs
cluster, durable vs transient, < 100 runs/day vs > 1000 runs/day), which
combination of `TapestryStore` / `RunHistory` / `DataStore` to pick.

Examples:
- "Local dev": `InMemory*` (default).
- "Single-host durable": `SQLiteStore` + `SQLiteHistory` + `LocalDiskDataStore`.
- "Distributed lineage analytics": `PostgresStore` + `DuckDBHistory` (yes,
  two databases — Postgres for OLTP writes, DuckDB for OLAP reads against a
  read replica).
- "High-volume distributed runs": `PostgresStore` + `PostgresHistory` +
  `S3DataStore`.

### 5.3 — OpenTelemetry wiring guide

**Where:** new file `docs/observability.md`.

**Content:** end-to-end trace setup. How to configure
`opentelemetry-sdk` to export to a collector, how `OpenTelemetryEmitter`
spans nest under a parent run span, how to filter by `pirn.run_id` /
`pirn.knot_id` in Jaeger or Tempo.

Code: a working snippet that produces real traces, screenshots of the
result.

### 5.4 — Migration guide from Phase 2 to Phase 3

**Where:** new file `docs/migration-phase2-to-phase3.md`.

**Content:** mostly "nothing to do — the API is additive." But spell out:
- Default backends are unchanged (`InMemory*`).
- The `emitters=` parameter on `Tapestry` is new and optional.
- The `extensible=` parameter on `Tapestry.run` is new and optional.
- Pyproject extras are new; no behavior change unless installed.

---

## Priority 6 — Cleanup and polish

Small items that don't block anything but improve the codebase.

### 6.1 — Audit `# type: ignore` comments

**Where:** scattered through `pirn/`. Run `grep -rn "type: ignore" pirn/`,
review each. Most are legitimate (lazy imports, `Any` callbacks); some may
be removable now that pyright config is in place.

**Acceptance:** every remaining `# type: ignore` has a comment explaining
why.

### 6.2 — Replace string-style type hints in remaining places

The fixes I made to `triggers/base.py` and `streaming/base.py` removed the
`KnotSubscriber = "callable[[Knot], None]"` antipattern. A grep for similar
patterns would catch any I missed:

```bash
grep -rn '= "callable\[' pirn/
grep -rn '= "[A-Z].*\[' pirn/  # any other stringified type assignments
```

**Acceptance:** no stringified type aliases remain except where needed for
forward references.

### 6.3 — Tighten ValKey aregister race

The current `register()` (sync wrapper) caches the live knot eagerly and
fires the async write as a background task. There's a window where:

1. Process A calls `register(knot)` — knot lands in `_live` cache.
2. Process A's async task hasn't completed yet.
3. Process A crashes.

The knot is in `_live` but not in ValKey. On restart, the knot is gone.

**Fix:** for production correctness, `register()` shouldn't return until
the write has hit ValKey. Either:
- Make `register()` synchronous (block on the loop).
- Document that `aregister()` is the production path; `register()` is best-
  effort only.

Right now the test uses `aregister` and verifies the write; production
should follow the same pattern. Add a docstring warning to `register()`.

### 6.4 — `SQLiteStore` and `SQLiteHistory` should support a connection-pool option

Right now they take one `sqlite3.Connection`. SQLite allows multiple
read connections + one write connection (WAL mode). For higher concurrency,
add a small pool wrapper or document that single-writer is the model.

**Acceptance:** docstring update at minimum; pool implementation if needed.

### 6.5 — Default emitter list cleanup

`Tapestry.add_emitter` exists but `remove_emitter` doesn't. Symmetric API
would be nice. Also: `Tapestry.emitters` returns a copy each time (good)
but doesn't expose any way to inspect *what's subscribed during a run*.

**Acceptance:** `add_emitter` / `remove_emitter` symmetric pair; test that
`remove_emitter` removes by identity, not equality.

---

## Priority 7 — Speculative / out-of-scope-but-worth-mentioning

These are bigger questions that probably don't belong in Phase 3 but are
worth flagging.

### 7.1 — Stateful streaming operators

The current streaming model runs one whole tapestry per tick. A more
ambitious model would let downstream knots accumulate state across ticks
(windowed aggregations, sessionization, joins). That requires a fundamentally
different execution model — closer to Flink than to a request/response
engine. Probably a separate package (`pirn-stream` or similar).

### 7.2 — A web UI for browsing run history

`html_for_run` produces a single-file standalone visualization for *one*
run. A real ops UI would let you browse runs by date, filter by status, drill
into lineage, replay failed runs with corrected parameters. That's a
non-trivial frontend project; consider whether it should be in-tree or a
separate `pirn-ui` package.

### 7.3 — Run-replay tooling

Given a `RunResult`, reconstruct the original `RunRequest` and re-run with
modified parameters or a different code version, then diff the two runs by
output hash. Useful for debugging, regression tests, and "what if" analysis.

API sketch:
```python
from pirn import replay_run
new_result = await replay_run(
    history=t.history,
    run_id="run-abc",
    tapestry=t,
    parameter_overrides={"x": 99},
)
# Compare:
diff = compare_runs(original_result, new_result)  # returns per-knot diffs
```

### 7.4 — Compile-time pipeline validation

Tapestry validation today is runtime — `t.run()` discovers missing
parameters, type mismatches, cycles. A `tapestry_check` CLI that statically
analyzes a tapestry definition module and reports issues (à la mypy) would
catch problems earlier.

### 7.5 — Pydantic v3 migration

Pyproject pins `pydantic>=2.0`. Pydantic v3 is on the horizon (or already
out by the time this is read). Plan: ensure all `model_dump_json` /
`model_validate_json` usages are forward-compatible; track v3 release notes.

---

## Suggested execution order

If picking these up sequentially:

1. **Priority 1.8** (S3 endpoint_url) — small fix, unblocks 1.5.
2. **Priority 1.1** (docker-compose) — gives you the environment.
3. **Priority 1.2** (Postgres real tests) — highest-value real-backend
   suite.
4. **Priority 1.3, 1.4, 1.5** (ValKey, Kafka, S3 real tests) — parallelizable.
5. **Priority 1.7** (CI workflow) — wires everything together.
6. **Priority 1.6** (Dask/Ray/Celery real tests) — last in P1; flakiest.
7. **Priority 3.1** (schema versions) — needed before anyone deploys to
   production.
8. **Priority 5.1** (examples) — improves adoption ahead of any further
   feature work.
9. **Priority 4.1** (perf baselines) — establish numbers before optimizing.
10. **Priority 4.2** (lineage batching) — informed by 4.1's findings.
11. **Priority 2** (subscribable distributed stores) — only when there's a
    real user request.
12. Everything else as the project's needs dictate.

Total realistic effort estimate: priorities 1–3 are roughly 2 weeks of
focused work; priorities 4–6 another 1–2 weeks; priority 7 is open-ended.
