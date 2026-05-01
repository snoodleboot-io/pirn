"""Cross-cutting Source/Sink connector knots.

Connectors are organized by category and ship behind per-backend optional
extras so users only install the dependencies they need::

    pip install 'pirn[postgres]'
    pip install 'pirn[snowflake,kafka,s3]'
    pip install 'pirn[all-db,all-storage,all-stream]'

Each connector's submodule calls :func:`pirn.domains._extras.require_extra`
to fail fast if its specific extra is not installed.

Categories
----------
- ``databases/``       — Postgres, MySQL, BigQuery, Snowflake, Redshift, ClickHouse, Databricks, DuckDB, MSSQL, Oracle, SQLite
- ``object_storage/``  — S3, GCS, Azure Blob, local filesystem, HDFS
- ``streaming/``       — Kafka, Kinesis, PubSub, RabbitMQ, Azure Service Bus, Valkey Streams
- ``saas/``            — Salesforce, HubSpot, Stripe, GitHub, Jira, Shopify, ...
- ``bi_catalog/``      — dbt Artifacts, Fivetran, Airbyte, DataHub, OpenMetadata, Alation
- ``observability/``   — OpenTelemetry, Datadog, Prometheus, Grafana
"""

# No top-level extras requirement: each connector module enforces its own.

__all__: list[str] = []
