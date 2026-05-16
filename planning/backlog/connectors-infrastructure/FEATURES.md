# Features: Connectors Infrastructure

**Status:** Backlog

---

## Feature: Credential and Connection Lifecycle Infrastructure

Foundational infrastructure that all connector knots depend on.

### Story: Connector configs handle credentials safely and consistently

#### Tasks
- Implement `CredentialProvider` interface in `pirn/domains/connectors/`
- Implement `EnvVarCredentialProvider` — reads credentials from environment variables at connect time
- Implement `SecretStrCredentialConfig` mixin — wraps sensitive fields with masking repr for use in connector config dataclasses
- Update all existing connector config dataclasses to use `CredentialProvider` or `SecretStrCredentialConfig`

### Story: Connection lifecycle is managed by pool classes; knots receive pools via injection

#### Tasks
- Codify pool injection contract: all knots accept pool via constructor; no knot instantiates a pool in `process()`
- Implement `PoolAwareKnot` mixin that validates pool is initialised before `process()` is called
- Update `DatabaseConnectionPoolKnot` to work as the canonical pool lifecycle manager for tapestries

---

## Feature: Relational Database and Data Warehouse Knots

Knots for bulk load, merge-upsert, DDL, and schema inspection across relational backends.

### Story: Data engineers can bulk-load data using database-native protocols

#### Tasks
- Implement `PostgresCopySource` — reads from Postgres using COPY TO STDOUT; yields `DataBatch` rows
- Implement `PostgresCopySink` — writes `DataBatch` to Postgres using COPY FROM STDIN
- Implement `BigQueryLoadJobSink` — writes `DataBatch` to BigQuery using a load job (not streaming insert)
- Implement `BigQueryQuerySource` — reads query results from BigQuery into `DataBatch`
- Implement `SnowflakePutCopySink` — stages `DataBatch` to Snowflake internal stage via PUT then COPY INTO
- Implement `SnowflakeQuerySource` — reads query results from Snowflake into `DataBatch`

### Story: Data engineers can inspect and evolve database schemas

#### Tasks
- Implement `DatabaseSchemaInspectorSource` — emits table schema as `DataSchema`; works for Postgres, MySQL, DuckDB
- Implement `DatabaseDDLExecuteSink` — executes DDL statements (CREATE, ALTER, DROP) against any pool-backed database

### Story: Data engineers can connect to ClickHouse, Databricks, and Dremio

#### Tasks
- Implement `ClickHouseQuerySource` and `ClickHouseInsertSink`
- Implement `DatabricksQuerySource` and `DatabricksSink` (using Databricks Connect or JDBC)
- Implement `DremioQuerySource` via Arrow Flight

---

## Feature: Cloud Object Storage Knots

Advanced object storage operations beyond basic read/write.

### Story: Engineers can list, copy, and manage objects with glob and prefix filters

#### Tasks
- Implement `ObjectStoreGlobListSource` — lists objects matching a glob pattern; emits object keys as `DataBatch`
- Implement `ObjectStoreCopyKnot` — copies objects between keys or buckets within the same backend
- Implement `ObjectStoreDeleteSink` — deletes objects by key; accepts `DataBatch` of keys
- Implement `ObjectStorePresignedUrlKnot` — generates time-limited presigned URLs for S3/GCS/Azure

### Story: Engineers can upload large files using multi-part upload

#### Tasks
- Implement `S3MultipartUploadSink` — splits large data streams into S3 multi-part upload parts
- Implement `GCSResumableUploadSink` — uses GCS resumable upload API for large objects

---

## Feature: Streaming / Message Broker Knots

Consumer-side and operational knots for streaming backends.

### Story: Engineers can consume from Kafka with consumer group management

#### Tasks
- Implement `KafkaConsumerSource` — consumes from a Kafka topic with configurable consumer group; yields `DataBatch` per poll
- Implement `KafkaDeadLetterSink` — routes failed messages to a configured dead-letter topic
- Implement `KafkaOffsetCommitKnot` — commits consumer offsets after downstream knot confirms processing

### Story: Engineers can consume from PubSub, Kinesis, and RabbitMQ

#### Tasks
- Implement `PubSubSubscriberSource` — pulls messages from a PubSub subscription; yields `DataBatch`
- Implement `KinesisShardReaderSource` — reads from a Kinesis shard with configurable starting position
- Implement `RabbitMQConsumerSource` — consumes from a RabbitMQ queue; yields `DataBatch` per message batch

---

## Feature: Document Database Knots

Knots for MongoDB, Firestore, ArangoDB, and Couchbase.

### Story: Engineers can query and write documents to MongoDB

#### Tasks
- Implement `MongoQuerySource` — executes a MongoDB find/aggregate query; yields `DataBatch` of documents
- Implement `MongoInsertSink` — inserts `DataBatch` documents into a MongoDB collection
- Implement `MongoUpdateSink` — applies update spec to matching documents in a collection

### Story: Engineers can query and write to Firestore and ArangoDB

#### Tasks
- Implement `FirestoreQuerySource` and `FirestoreWriteSink`
- Implement `ArangoQuerySource` (AQL) and `ArangoInsertSink`
- Implement `CouchbaseQuerySource` (N1QL) and `CouchbaseUpsertSink`

---

## Feature: Graph Database Knots

Knots for Neo4j, Memgraph, and OrientDB.

### Story: Engineers can execute Cypher queries and write graph data

#### Tasks
- Implement `Neo4jCypherSource` — executes a Cypher read query; yields `DataBatch` of result rows
- Implement `Neo4jCypherSink` — executes a Cypher write query with `DataBatch` parameters
- Implement `MemgraphCypherSource` and `MemgraphCypherSink`
- Implement `OrientDBQuerySource` (SQL dialect) and `OrientDBInsertSink`

---

## Feature: Time-Series Database Knots

Knots for InfluxDB, TimescaleDB, QuestDB, VictoriaMetrics, and kdb+.

### Story: Engineers can write and query time-series data

#### Tasks
- Implement `InfluxDBWriteSource` — reads time-range from InfluxDB bucket via Flux query; yields `DataBatch`
- Implement `InfluxDBWriteSink` — writes `DataBatch` to InfluxDB line protocol endpoint
- Implement `TimescaleDBQuerySource` and `TimescaleDBInsertSink` (via Postgres pool)
- Implement `QuestDBILPSink` — writes `DataBatch` via QuestDB InfluxDB Line Protocol
- Implement `VictoriaMetricsQuerySource` (PromQL) and `VictoriaMetricsWriteSink`
- Implement `KdbQuerySource` and `KdbInsertSink` via kdb+ IPC

---

## Feature: SaaS API Knots

Read-path knots wrapping each SaaS client config.

### Story: Data engineers can extract records from CRM, billing, and marketing platforms

#### Tasks
- Implement `SalesforceQuerySource` — executes SOQL query via simple_salesforce; yields `DataBatch`
- Implement `HubSpotListSource` — pages through HubSpot CRM objects; yields `DataBatch`
- Implement `StripeEventSource` — pages through Stripe events; yields `DataBatch`
- Implement `ShopifyOrderSource` — pages through Shopify orders via REST or GraphQL; yields `DataBatch`
- Implement `ZendeskTicketSource` — pages through Zendesk tickets; yields `DataBatch`

### Story: Data engineers can extract events from analytics and product platforms

#### Tasks
- Implement `MixpanelEventSource`, `AmplitudeEventSource`, `GoogleAnalyticsReportSource`
- Implement `GitHubIssueSource`, `JiraIssueSource`
- Implement `AirtableTableSource`, `TwilioMessageSource`

---

## Feature: BI / Catalog Knots

Knots for dbt artifacts, Airbyte, Fivetran, DataHub, and OpenMetadata.

### Story: Data engineers can read dbt artifacts and push metadata to a catalog

#### Tasks
- Implement `DbtArtifactsSource` — reads dbt `manifest.json` and `run_results.json`; yields structured `DataBatch` of models and test results
- Implement `DataHubMetadataPushSink` — pushes lineage and schema metadata to DataHub REST emitter
- Implement `OpenMetadataEntitySink` — pushes entity metadata to OpenMetadata API

### Story: Data engineers can trigger and monitor sync jobs

#### Tasks
- Implement `AirbyteSyncTriggerKnot` — triggers an Airbyte connection sync; polls for completion
- Implement `FivetranSyncTriggerKnot` — triggers a Fivetran connector sync; polls for completion
- Implement `AlationMetadataSource` — reads table and column metadata from Alation catalog; yields `DataBatch`
