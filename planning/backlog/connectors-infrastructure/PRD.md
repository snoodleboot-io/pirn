# PRD: Connectors Infrastructure

**Status:** Backlog
**Initiative:** connectors-infrastructure
**Depends on:** domain-knot-libraries (complete)

---

## Problem

The domain-knot-libraries initiative shipped config and pool classes for 80+ connector backends. However, the generic knot layer (`DatabaseQuerySource`, `DatabaseExecuteSink`, `ObjectStoreReadSource`, `MessageBrokerPublishSink`) only covers the three I/O primitives: query, execute, and publish. Practitioners need richer, connector-specific knots for:

- **Relational databases and warehouses:** Bulk load operations, COPY protocol, merge-upsert, DDL execution, and schema inspection are not covered by a generic `DatabaseExecuteSink`.
- **Cloud object storage:** Multi-part upload, prefix listing with glob filters, and signed URL generation are not exposed.
- **Streaming:** Consumer group management, offset reset, dead-letter queue routing, and exactly-once delivery confirmation are not covered by `MessageBrokerPublishSink`.
- **Document, graph, and time-series databases:** These have configs and pools but no knots. There is no `MongoQuerySource`, `Neo4jCypherSink`, or `InfluxDBWriteSource`.
- **SaaS and BI/catalog connectors:** Config and client classes exist but no pirn Knot wraps them. Users cannot compose Salesforce, HubSpot, or dbt artifacts into a tapestry without writing their own Knot subclasses.
- **Credential and connection lifecycle:** No standard credential injection pattern exists. Each domain knot author currently handles credentials differently — some via constructor args, some via environment variables, some via config dataclasses. There is no `CredentialProvider` abstraction.

Approximately 48 named connector knot classes are missing across these categories.

## Goal

Ship the missing connector knots and the supporting infrastructure (credential injection, connection lifecycle, batch sizing, backpressure) so practitioners can compose any supported backend into a pirn tapestry without writing custom Knot subclasses.

## Success Criteria

- All 48 missing connector knot classes are implemented with real SDK calls
- A `CredentialProvider` abstraction exists; all connector configs use it
- Connection pool lifecycle is managed by the pool class; knots never open or close connections directly
- Bulk load knots exist for Postgres (COPY), BigQuery (load job), and Snowflake (PUT + COPY INTO)
- Document DB knots exist for MongoDB, Firestore, and ArangoDB
- Graph DB knots exist for Neo4j and Memgraph
- Time-series DB knots exist for InfluxDB, TimescaleDB, and QuestDB
- SaaS knots wrap at least the read path for all 12 existing SaaS client configs
- BI/catalog knots wrap dbt artifacts reader, Airbyte sync trigger, and DataHub metadata push

## Out of Scope

- Implementing new connector backends not already represented by a config/pool class
- Real-time streaming exactly-once semantics (tracked separately; requires engine-level transaction support)
- OAuth token refresh flows within the knot layer (credential providers handle this outside knot `process()`)
