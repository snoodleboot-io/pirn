# Real-backend testing plan

Phase 3 ships with mock-driver tests for every networked backend
(Postgres, ValKey, Kafka, S3) so the suite runs cleanly on a laptop
with zero infrastructure. This document describes how to run the
**real**-backend tests — the ones gated by the `@pytest.mark.needs_*`
markers — locally via Docker Compose and in CI via Kubernetes.

The mock tests verify that pirn's adapter layer issues the correct
calls. The real-backend tests verify that those calls produce the
right behavior against a genuine server. Both matter; this plan covers
the second category.

## What's gated

The following pytest markers identify tests that require live
infrastructure:

| Marker            | Required service          | Env var                  |
| ----------------- | ------------------------- | ------------------------ |
| `needs_postgres`  | PostgreSQL ≥ 14           | `PIRN_TEST_POSTGRES_URL` |
| `needs_valkey`    | ValKey ≥ 8 or Redis ≥ 7   | `PIRN_TEST_VALKEY_URL`   |
| `needs_kafka`     | Kafka 3.x or Redpanda     | `PIRN_TEST_KAFKA_URL`    |
| `needs_s3`        | S3 / MinIO / LocalStack   | `PIRN_TEST_S3_*` (below) |

Tests with these markers skip silently when the env var is unset, so
they're safe to leave in the suite.

The real-backend tests will be added alongside the existing mock tests
under `tests/integration/` with file names like `test_postgres_real.py`.
The convention: each `test_<backend>_real.py` mirrors the mock file's
test list, swapping the fake driver for a fixture that connects to
the real instance.

## Local dev: Docker Compose

The fastest path to a working real-backend suite on a laptop. Save
this as `docker-compose.test.yml` at the repo root:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: pirn
      POSTGRES_PASSWORD: pirn
      POSTGRES_DB: pirn_test
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pirn"]
      interval: 1s
      timeout: 1s
      retries: 30

  valkey:
    image: valkey/valkey:8-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 1s
      timeout: 1s
      retries: 30

  redpanda:
    # Redpanda is a Kafka-API-compatible broker; faster cold-start than
    # full Kafka and a single image (no ZooKeeper or KRaft setup).
    image: redpandadata/redpanda:latest
    command:
      - redpanda
      - start
      - --overprovisioned
      - --smp=1
      - --memory=512M
      - --reserve-memory=0M
      - --check=false
      - --node-id=0
      - --kafka-addr=PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr=PLAINTEXT://localhost:9092
    ports: ["9092:9092"]

  minio:
    # MinIO is S3-API-compatible; LocalStack is the alternative if you
    # also want SQS/SNS/etc. emulation.
    image: minio/minio:latest
    command: server /data
    environment:
      MINIO_ROOT_USER: pirn
      MINIO_ROOT_PASSWORD: pirntestpassword
    ports: ["9000:9000"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 1s
      timeout: 1s
      retries: 30
```

Bring it up:

```bash
docker compose -f docker-compose.test.yml up -d
```

Set the env vars and run:

```bash
export PIRN_TEST_POSTGRES_URL="postgresql://pirn:pirn@localhost:5432/pirn_test"
export PIRN_TEST_VALKEY_URL="redis://localhost:6379/0"
export PIRN_TEST_KAFKA_URL="localhost:9092"
export PIRN_TEST_S3_ENDPOINT="http://localhost:9000"
export PIRN_TEST_S3_ACCESS_KEY="pirn"
export PIRN_TEST_S3_SECRET_KEY="pirntestpassword"
export PIRN_TEST_S3_BUCKET="pirn-test"

# Create the bucket once (MinIO doesn't create it for you).
docker run --rm --network host minio/mc \
  alias set local http://localhost:9000 pirn pirntestpassword
docker run --rm --network host minio/mc mb local/pirn-test || true

# Run only the real-backend tests.
.venv/bin/pytest -q -m "needs_postgres or needs_valkey or needs_kafka or needs_s3"
```

Tear down when done:

```bash
docker compose -f docker-compose.test.yml down -v
```

## Per-test fixture pattern

Each real-backend test file declares a `pytest` fixture that:

1. Reads the env var; skips with a helpful message if absent.
2. Connects to the service.
3. Yields the connection / pool / client.
4. Cleans up after the test (truncates tables, deletes keys, etc.) so
   tests don't leak state into each other.

Sketch for Postgres:

```python
# tests/integration/test_postgres_real.py
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
    # Each test gets clean tables.
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS knots, runs, lineage, lineage_inputs CASCADE")
    yield pool
    await pool.close()


async def test_postgres_history_round_trips(pg_pool):
    from pirn.backends.postgres import PostgresHistory
    from pirn import Tapestry, Parameter, KnotConfig, RunRequest, knot

    @knot
    async def double(x: int) -> int:
        return x * 2

    history = PostgresHistory(pool=pg_pool)
    with Tapestry(history=history) as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        double(x=p, _config=KnotConfig(id="d"))
    result = await t.run(RunRequest(parameters={"x": 5}))

    fetched = await history.get_run(result.run_id)
    assert fetched.run_id == result.run_id
    assert fetched.outputs == result.outputs
```

Symmetric scaffolding for ValKey, Kafka, and S3 lives in the same
directory — `test_valkey_real.py`, `test_kafka_real.py`, `test_s3_real.py`.

## CI: GitHub Actions

A workflow that brings the same services up via service containers
and runs the gated tests:

```yaml
# .github/workflows/real-backends.yml
name: real-backends
on: [pull_request, push]

jobs:
  real-backends:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: pirn
          POSTGRES_PASSWORD: pirn
          POSTGRES_DB: pirn_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U pirn"
          --health-interval 1s
          --health-timeout 1s
          --health-retries 30

      valkey:
        image: valkey/valkey:8-alpine
        ports: ["6379:6379"]

      redpanda:
        image: redpandadata/redpanda:latest
        ports: ["9092:9092"]
        env:
          REDPANDA_MODE: dev-container

      minio:
        image: minio/minio:latest
        ports: ["9000:9000"]
        env:
          MINIO_ROOT_USER: pirn
          MINIO_ROOT_PASSWORD: pirntestpassword

    env:
      PIRN_TEST_POSTGRES_URL: postgresql://pirn:pirn@localhost:5432/pirn_test
      PIRN_TEST_VALKEY_URL: redis://localhost:6379/0
      PIRN_TEST_KAFKA_URL: localhost:9092
      PIRN_TEST_S3_ENDPOINT: http://localhost:9000
      PIRN_TEST_S3_ACCESS_KEY: pirn
      PIRN_TEST_S3_SECRET_KEY: pirntestpassword
      PIRN_TEST_S3_BUCKET: pirn-test

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e '.[dev,all]'
      - run: |
          # Create MinIO bucket.
          curl -fsSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /tmp/mc
          chmod +x /tmp/mc
          /tmp/mc alias set local http://localhost:9000 pirn pirntestpassword
          /tmp/mc mb local/pirn-test || true
      - run: pytest -q -m "needs_postgres or needs_valkey or needs_kafka or needs_s3"
```

Note: GitHub Actions service containers don't support `command:` for
overriding the image entrypoint, so Redpanda/MinIO must run with
their default entrypoints. Both work fine; this is just a constraint
to know about.

## Kubernetes: integration cluster

For staging-environment tests against a long-running cluster (the
right place to verify cluster-mode ValKey, multi-broker Kafka,
real S3 with cross-region behavior), deploy with Helm charts:

| Service     | Chart                                         |
| ----------- | --------------------------------------------- |
| PostgreSQL  | `bitnami/postgresql` or `bitnami/postgresql-ha` |
| ValKey      | `bitnami/valkey-cluster`                      |
| Kafka       | `bitnami/kafka` or `strimzi/strimzi-kafka-operator` |
| S3          | use real AWS S3 with a test bucket            |

The CI runs against a dedicated namespace; tests use Kubernetes
service DNS for connection URLs:

```
PIRN_TEST_POSTGRES_URL=postgresql://pirn:pirn@postgres.pirn-test.svc.cluster.local:5432/pirn_test
PIRN_TEST_VALKEY_URL=redis://valkey-cluster.pirn-test.svc.cluster.local:6379/0
PIRN_TEST_KAFKA_URL=kafka.pirn-test.svc.cluster.local:9092
```

State cleanup between test runs is critical — use a per-job database
name suffix (e.g., `pirn_test_${CI_JOB_ID}`) for Postgres, prefix
all ValKey keys with `${CI_JOB_ID}:`, give Kafka a unique consumer
group, and use a per-job bucket prefix for S3.

## What the real-backend tests should cover

At minimum, the same scenarios as the mock tests, plus a few that
only matter against a real server:

* **Concurrency**: 100 parallel `record_run` calls succeed without
  deadlock or duplicate-key errors. (Mock tests have no real
  contention.)
* **Persistence**: write data with one connection, close it, open a
  new one, read the data back. (Mocks store in-memory dicts that go
  away when the test ends — they can't catch a missing `commit`.)
* **Schema migration safety**: bring up two pirn versions in
  parallel; verify the older one keeps working after the newer one
  upgrades the schema. (Mock tests don't run DDL twice.)
* **Failure modes**: kill the connection mid-write (Postgres
  `pg_terminate_backend`); verify the dispatcher's retry / error
  handling. (Mocks can simulate this but rarely do — real failure
  injection is more honest.)
* **TTL behavior** (ValKey, S3 lifecycle): write with a short TTL,
  wait, verify the value is gone.

## Why not just real-backend tests?

A few reasons mocks earn their keep:

* **Speed.** The full suite runs in 4 seconds with mocks. Real
  backends add 30+ seconds per service for connection setup alone.
  Fast feedback loops matter.
* **Determinism.** Real services occasionally flake (cold-start
  timing, clock skew, network blips). Mocks don't. CI runs both
  layers; a mock failure is always a real bug, while a real-backend
  flake gets a retry.
* **Coverage of error paths.** Some error paths (driver-level
  serialization failures, connection-pool exhaustion) are easier to
  exercise with a fake than with a real server.

The two layers complement each other: mocks for adapter logic and
SQL/binding correctness, real backends for behavior.
