# PRD: Connectors Infrastructure

**Status:** Backlog
**Priority:** High

---

## Problem Statement

Pirn's domain libraries require Source and Sink knots that speak to real external systems — relational databases, object storage, streaming platforms, SaaS APIs, and BI catalogs. Today, none of these exist. Users who need a `PostgresSource`, `S3Sink`, or `KafkaSource` must write their own from scratch, choosing their own dependency, handling their own connection lifecycle, and inventing their own data contract.

This is the single largest gap between pirn as a framework and pirn as a platform. Without standard connectors, every new pipeline author starts from zero for the most common integration tasks.

---

## Goals

- Ship a standard library of Source and Sink knots for the most common external systems
- Ensure each connector is independently installable via an optional extra (`pip install pirn[postgres]`, `pirn[s3]`, etc.)
- Establish a shared `ConnectorConfig` contract so connector implementations are interchangeable at the pipeline level
- Make connectors KnotRegistry-composable (YAML-declarable)
- Keep the base `pirn` install slim — no connector dependency leaks into the core

---

## Scope

### Category 1: Relational Databases

| Connector | Source | Sink | Optional Extra | Backing Library |
|-----------|--------|------|---------------|-----------------|
| `PostgresConnector` | `PostgresSource` | `PostgresSink` | `pirn[postgres]` | `psycopg3` |
| `MySQLConnector` | `MySQLSource` | `MySQLSink` | `pirn[mysql]` | `mysql-connector-python` |
| `RedshiftConnector` | `RedshiftSource` | `RedshiftSink` | `pirn[redshift]` | `redshift-connector` |
| `ClickHouseConnector` | `ClickHouseSource` | `ClickHouseSink` | `pirn[clickhouse]` | `clickhouse-connect` |

All relational connectors share: connection pooling, parameterized queries, schema inference on read, upsert/insert/replace strategies on write.

### Category 2: Cloud Object Storage & File Formats

| Connector | Source | Sink | Optional Extra | Backing Library |
|-----------|--------|------|---------------|-----------------|
| `S3Connector` | `S3Source` | `S3Sink` | `pirn[s3]` | `boto3` |
| `GCSConnector` | `GCSSource` | `GCSSink` | `pirn[gcs]` | `google-cloud-storage` |
| `AzureBlobConnector` | `AzureBlobSource` | `AzureBlobSink` | `pirn[azure]` | `azure-storage-blob` |

File format knots (format is orthogonal to storage backend):

| Knot | Direction | Extra | Backing Library |
|------|-----------|-------|-----------------|
| `CSVFormat` | read/write | `pirn[csv]` (stdlib, no extra needed) | `csv` / Polars |
| `ParquetFormat` | read/write | `pirn[parquet]` | `pyarrow` |
| `JSONFormat` | read/write | `pirn[json]` (stdlib, no extra needed) | `json` / `orjson` |
| `ArrowFormat` | read/write | `pirn[arrow]` | `pyarrow` |
| `DeltaFormat` | read/write | `pirn[delta]` | `deltalake` |
| `IcebergFormat` | read/write | `pirn[iceberg]` | `pyiceberg` |

### Category 3: Streaming & Messaging

| Connector | Source | Sink | Optional Extra | Backing Library |
|-----------|--------|------|---------------|-----------------|
| `KafkaConnector` | `KafkaSource` | `KafkaSink` | `pirn[kafka]` | `confluent-kafka` |
| `KinesisConnector` | `KinesisSource` | `KinesisSink` | `pirn[kinesis]` | `boto3` |
| `PubSubConnector` | `PubSubSource` | `PubSubSink` | `pirn[pubsub]` | `google-cloud-pubsub` |
| `RedisStreamConnector` | `RedisStreamSource` | `RedisStreamSink` | `pirn[redis]` | `redis-py` |

All streaming connectors share: consumer group management, offset commit semantics, batch accumulation, backpressure handling.

### Category 4: Cloud Data Warehouses

| Connector | Source | Sink | Optional Extra | Backing Library |
|-----------|--------|------|---------------|-----------------|
| `BigQueryConnector` | `BigQuerySource` | `BigQuerySink` | `pirn[bigquery]` | `google-cloud-bigquery` |
| `SnowflakeConnector` | `SnowflakeSource` | `SnowflakeSink` | `pirn[snowflake]` | `snowflake-connector-python` |
| `DatabricksConnector` | `DatabricksSource` | `DatabricksSink` | `pirn[databricks]` | `databricks-sql-connector` |
| `TrinoConnector` | `TrinoSource` | `TrinoSink` | `pirn[trino]` | `trino` |

### Category 5: SaaS APIs

| Connector | Source | Sink | Optional Extra | Notes |
|-----------|--------|------|---------------|-------|
| `SalesforceConnector` | `SalesforceSource` | — | `pirn[salesforce]` | SOQL queries, bulk API |
| `HubSpotConnector` | `HubSpotSource` | — | `pirn[hubspot]` | CRM objects via v3 API |
| `StripeConnector` | `StripeSource` | — | `pirn[stripe]` | Events, charges, customers |
| `GoogleAnalyticsConnector` | `GoogleAnalyticsSource` | — | `pirn[ga]` | GA4 Data API |
| `SlackConnector` | `SlackSource` | `SlackSink` | `pirn[slack]` | Messages, channels; sink posts messages |
| `NotionConnector` | `NotionSource` | `NotionSink` | `pirn[notion]` | Pages and databases |

### Category 6: BI, Catalog & Observability Sinks

| Connector | Direction | Optional Extra | Notes |
|-----------|-----------|---------------|-------|
| `DataCatalogSink` | sink | `pirn[catalog]` | Pluggable — OpenMetadata, DataHub, Amundsen |
| `OpenMetadataConnector` | source/sink | `pirn[openmetadata]` | Full lineage push |
| `DatadogSink` | sink | `pirn[datadog]` | Pipeline metrics and events |
| `PrometheusMetricsSink` | sink | `pirn[prometheus]` | Exposes pipeline counters via push gateway |
| `OpenTelemetrySink` | sink | `pirn[otel]` | Spans and metrics via OTLP |

**Total:** 48 connector classes across 6 categories.

---

## Out of Scope

- Connection pooling middleware (each connector manages its own pool)
- Schema migration tooling (tracked in domain-knot-specializations PRD under Schema Evolution)
- Custom authentication providers (connectors accept credentials via config; auth backends are user-supplied)
- Connector-to-connector direct streaming (pirn is an orchestrator; connectors produce/consume `DataBatch`)

---

## Success Criteria

1. Each of the 48 connector classes is implemented and importable under `pirn/domains/connectors/`
2. Each connector is independently installable via its optional extra without pulling other connector dependencies
3. The base `pip install pirn` installs zero connector dependencies
4. Each connector has a unit test using mocked/stubbed external calls
5. Each connector has an integration test (marked `pytest.mark.slow`) that exercises a real or containerized external system
6. All connectors are registered in the connectors `KnotRegistry`
7. A shared `ConnectorConfig` base class defines: `connection_timeout`, `retry_policy`, `credential_source`, `batch_size`
8. At least one end-to-end example pipeline demonstrates source → transform → sink using two different connector categories

---

## Technical Constraints

- **Dependency isolation is mandatory.** Each connector extra must be independently installable. A `pirn[postgres]` install must not pull in `boto3`, `confluent-kafka`, or any other connector library. Use `try/except ImportError` guards in all connector modules and raise a clear `MissingDependencyError` with the correct `pip install` command.
- **No connector dependency in `pirn` core.** The `pirn` package `[project.dependencies]` in `pyproject.toml` must not list any connector library. All connector libraries live under `[project.optional-dependencies]`.
- **Connection lifecycle.** Each connector must implement `__enter__`/`__exit__` for connection management. Connections must be closed on pipeline teardown even on error paths.
- **Credential handling.** Connectors must not log credentials. Credential fields must be marked as `SecretStr` or equivalent and excluded from lineage records and audit logs.
- **DataBatch contract.** All connectors produce and consume the `DataBatch` contract defined in `pirn.domains.data`. This is the lingua franca between connectors and domain transform knots.
- **Tiered engine compatibility.** Connectors that return large datasets should return Polars `LazyFrame` or Ibis relations, not in-memory lists of dicts, to preserve push-down optimization at Tier 3.
