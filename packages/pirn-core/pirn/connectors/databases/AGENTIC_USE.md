`pirn.connectors.databases` provides `ConnectionConfig` and `DatabaseConnectionPool` implementations for 13 relational and analytical databases — it does not execute queries; use `knots/DatabaseQuerySource` and `knots/DatabaseExecuteSink` for that.

---

## Mental model

Each database has a pair of files: `{db}_config.py` (credentials and DSN fields, a `ConnectionConfig` subclass) and `{db}_pool.py` (live connection pool, a `DatabaseConnectionPool` subclass). Create the config, pass it to the pool constructor, then pass the pool as a config constant to knots. Pools are lazy — connections open on first use.

---

## Source map

```
pirn/domains/connectors/databases/
├── postgres_config.py      PostgresConfig       — host, port, database, user, password, ssl_mode
├── postgres_pool.py        PostgresPool         — asyncpg-backed async pool
├── sqlite_config.py        SqliteConfig         — path, check_same_thread
├── sqlite_pool.py          SqlitePool           — aiosqlite-backed async pool
├── mysql_config.py         MySQLConfig          — host, port, database, user, password, charset
├── mysql_pool.py           MySQLPool            — aiomysql-backed async pool
├── mssql_config.py         MssqlConfig          — host, port, database, user, password, driver
├── mssql_pool.py           MssqlPool            — aioodbc-backed async pool
├── oracle_config.py        OracleConfig         — host, port, service_name, user, password
├── oracle_pool.py          OraclePool           — python-oracledb async pool
├── duckdb_config.py        DuckdbConfig         — path (in-memory or file), read_only
├── duckdb_pool.py          DuckdbPool           — duckdb async connection
├── bigquery_config.py      BigqueryConfig       — project, dataset, credentials_json
├── bigquery_pool.py        BigqueryPool         — google-cloud-bigquery client wrapper
├── snowflake_config.py     SnowflakeConfig      — account, warehouse, database, schema, role
├── snowflake_pool.py       SnowflakePool        — snowflake-connector-python async wrapper
├── redshift_config.py      RedshiftConfig       — host, port, database, user, password, ssl
├── redshift_pool.py        RedshiftPool         — redshift_connector async wrapper
├── databricks_config.py    DatabricksConfig     — server_hostname, http_path, access_token
├── databricks_pool.py      DatabricksPool       — databricks-sql-connector wrapper
├── clickhouse_config.py    ClickhouseConfig     — host, port, database, user, password, secure
├── clickhouse_pool.py      ClickhousePool       — clickhouse-connect async client
├── dremio_config.py        DremioConfig         — host, port, token, tls
└── dremio_pool.py          DremioPool           — pyarrow Flight client wrapper
```

---

## Canonical pattern

```python
from pirn.connectors.databases.postgres_config import PostgresConfig
from pirn.connectors.databases.postgres_pool import PostgresPool
from pirn.connectors.knots.database_query_source import DatabaseQuerySource
from pirn.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn import Tapestry, KnotConfig, RunRequest

config = PostgresConfig(host="db", port=5432, database="app", user="svc", password="s3cr3t")
pool   = PostgresPool(config=config)

with Tapestry() as t:
    rows    = DatabaseQuerySource(pool=pool, query="SELECT * FROM events", _config=KnotConfig(id="src"))
    scored  = ScoreKnot(rows=rows, _config=KnotConfig(id="score"))
    DatabaseExecuteSink(pool=pool, statement="INSERT INTO scored_events VALUES (:id, :score)",
                        rows=scored, _config=KnotConfig(id="sink"))

result = await t.run(RunRequest())
await pool.close()
```

---

## Anti-patterns

**Creating a pool inside the tapestry block** — pools are config constants, not knots. Build them outside the `with Tapestry()` block and reuse across runs.

**Storing raw passwords in code** — pass credentials via environment variables or a secrets manager; inject into `*Config` at construction.

---

## Constraints and gotchas

- **Each database requires its own extra.** e.g. `pirn[postgres]`, `pirn[snowflake]`, `pirn[bigquery]`. Check `pyproject.toml`.
- **`DuckdbConfig(path=":memory:")` creates a fresh in-memory DB per pool instance.** Use a file path for persistence.
- **`BigqueryPool` uses the synchronous BigQuery client wrapped in `asyncio.to_thread`.** Throughput is lower than native async pools.

---

## Quick reference

| Database | Config | Pool |
|---|---|---|
| PostgreSQL | `PostgresConfig` | `PostgresPool` |
| SQLite | `SqliteConfig` | `SqlitePool` |
| MySQL | `MySQLConfig` | `MySQLPool` |
| SQL Server | `MssqlConfig` | `MssqlPool` |
| Oracle | `OracleConfig` | `OraclePool` |
| DuckDB | `DuckdbConfig` | `DuckdbPool` |
| BigQuery | `BigqueryConfig` | `BigqueryPool` |
| Snowflake | `SnowflakeConfig` | `SnowflakePool` |
| Redshift | `RedshiftConfig` | `RedshiftPool` |
| Databricks | `DatabricksConfig` | `DatabricksPool` |
| ClickHouse | `ClickhouseConfig` | `ClickhousePool` |
| Dremio | `DremioConfig` | `DremioPool` |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
