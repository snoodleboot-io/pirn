`pirn.connectors.timeseries` provides `ConnectionConfig` and connection pool implementations for InfluxDB, TimescaleDB, QuestDB, kdb+, and VictoriaMetrics — it does not execute queries; use `DatabaseQuerySource` / `DatabaseExecuteSink` knots for that.

---

## Mental model

Each time-series database follows the same two-file pattern as `pirn.connectors.databases`: a `*Config` holding credentials and DSN fields, and a `*Pool` holding a live connection. Create the config, pass it to the pool, then pass the pool to knots. Pools are lazy — connections open on first use.

Time-series pools are interchangeable with `DatabaseConnectionPool` for query/execute knots. The distinction is that time-series databases have specialized write APIs (line protocol, ILP, tagged metrics) which may require vendor-specific knots.

---

## Source map

```
pirn/domains/connectors/timeseries/
├── influxdb_config.py        InfluxdbConfig        — url, token, org, bucket
├── influxdb_pool.py          InfluxdbPool          — InfluxDB v2 client (influxdb-client-python async)
├── timescaledb_config.py     TimescaledbConfig     — host, port, database, user, password, ssl_mode
├── timescaledb_pool.py       TimescaledbPool       — asyncpg-backed pool (TimescaleDB is PostgreSQL)
├── questdb_config.py         QuestdbConfig         — host, ilp_port, http_port, user, password
├── questdb_pool.py           QuestdbPool           — QuestDB ILP (line protocol) + REST query client
├── kdb_config.py             KdbConfig             — host, port, user, password
├── kdb_pool.py               KdbPool               — kdb+ q-IPC async client (qasync)
├── victoriametrics_config.py VictoriaMetricsConfig — url, tenant_id (for Cluster)
└── victoriametrics_pool.py   VictoriaMetricsPool   — VictoriaMetrics HTTP write + MetricsQL query client
```

---

## Canonical pattern

### InfluxDB — write metrics, query with Flux

```python
from pirn.connectors.timeseries.influxdb_config import InfluxdbConfig
from pirn.connectors.timeseries.influxdb_pool import InfluxdbPool
from pirn.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn import Tapestry, KnotConfig, RunRequest

pool = InfluxdbPool(config=InfluxdbConfig(
    url="http://influx:8086",
    token=os.environ["INFLUX_TOKEN"],
    org="my-org",
    bucket="metrics",
))

with Tapestry() as t:
    scored = ScoreKnot(_config=KnotConfig(id="score"))
    DatabaseExecuteSink(pool=pool,
                        statement="measurement,tag=:tag value=:value",
                        rows=scored,
                        _config=KnotConfig(id="write"))

result = await t.run(RunRequest())
await pool.close()
```

### TimescaleDB — query hypertable

```python
from pirn.connectors.timeseries.timescaledb_config import TimescaledbConfig
from pirn.connectors.timeseries.timescaledb_pool import TimescaledbPool
from pirn.connectors.knots.database_query_source import DatabaseQuerySource

pool = TimescaledbPool(config=TimescaledbConfig(
    host="timescale", port=5432, database="metrics", user="app", password="s3cr3t"
))

with Tapestry() as t:
    rows = DatabaseQuerySource(
        pool=pool,
        query="SELECT time, value FROM sensor_readings WHERE time > NOW() - INTERVAL '1 hour'",
        _config=KnotConfig(id="read"),
    )
```

---

## Anti-patterns

**Using `InfluxdbPool` with SQL-style `SELECT` statements** — InfluxDB v2 uses Flux or InfluxQL, not standard SQL. Pass Flux queries when using `DatabaseQuerySource` with `InfluxdbPool`.

**Forgetting that `TimescaledbPool` is PostgreSQL** — TimescaleDB extends PostgreSQL. All `asyncpg`-style parameters and connection limits apply. Treat it identically to `PostgresPool`.

---

## Constraints and gotchas

- **Each pool requires its own extra:** `pirn[influxdb]`, `pirn[timescaledb]`, `pirn[questdb]`, `pirn[kdb]`, `pirn[victoriametrics]`.
- **`QuestdbPool` exposes two ports:** ILP port 9009 for high-throughput writes (line protocol), HTTP port 9000 for queries. The pool constructor takes both.
- **`KdbPool` requires a running kdb+ q process.** The pool speaks the q-IPC binary protocol — it is not SQL.
- **`VictoriaMetricsPool` in cluster mode requires `tenant_id`** to route writes and queries to the correct tenant shard.

---

## Quick reference

| Database | Config | Pool | Extra |
|----------|--------|------|-------|
| InfluxDB v2 | `InfluxdbConfig` | `InfluxdbPool` | `pirn[influxdb]` |
| TimescaleDB | `TimescaledbConfig` | `TimescaledbPool` | `pirn[timescaledb]` |
| QuestDB | `QuestdbConfig` | `QuestdbPool` | `pirn[questdb]` |
| kdb+ | `KdbConfig` | `KdbPool` | `pirn[kdb]` |
| VictoriaMetrics | `VictoriaMetricsConfig` | `VictoriaMetricsPool` | `pirn[victoriametrics]` |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
