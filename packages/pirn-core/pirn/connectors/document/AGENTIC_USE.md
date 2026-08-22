`pirn.connectors.document` provides `ConnectionConfig` and connection pool implementations for MongoDB, ArangoDB, CouchDB, CouchBase, CosmosDB, and Firestore — it does not execute queries; use `DatabaseQuerySource` / `DatabaseExecuteSink` knots with document-store-specific query syntax.

---

## Mental model

Each document store follows the two-file pattern: a `*Config` (connection string or credentials) and a `*Pool` (live connection, `DatabaseConnectionPool` subclass). Create the config, pass it to the pool, then pass the pool to knots. All pools expose the standard `acquire()` / `release()` / `close()` interface so they are interchangeable with relational pools in knots.

Document query syntax is vendor-specific. Pass the native query language (MQL for MongoDB, AQL for ArangoDB, Mango for CouchDB/CouchBase, SQL API for CosmosDB, Firestore query DSL) as the `query=` string to `DatabaseQuerySource`.

---

## Source map

```
pirn/domains/connectors/document/
├── mongodb_config.py      MongoDBConfig      — uri, database, collection, tls
├── mongodb_pool.py        MongoDBPool        — motor async client
├── arangodb_config.py     ArangoDBConfig     — host, port, database, user, password, tls
├── arangodb_pool.py       ArangoDBPool       — python-arango async wrapper
├── couchdb_config.py      CouchDBConfig      — url, database, user, password
├── couchdb_pool.py        CouchDBPool        — aiocouch async client
├── couchbase_config.py    CouchbaseConfig    — connection_string, bucket, user, password
├── couchbase_pool.py      CouchbasePool      — couchbase-python-client async pool
├── cosmosdb_config.py     CosmosDBConfig     — endpoint, key, database, container
├── cosmosdb_pool.py       CosmosDBPool       — azure-cosmos async client
├── firestore_config.py    FirestoreConfig    — project, credentials_json, database
└── firestore_pool.py      FirestorePool      — google-cloud-firestore async client
```

---

## Canonical pattern

### MongoDB — query a collection

```python
from pirn.connectors.document.mongodb_config import MongoDBConfig
from pirn.connectors.document.mongodb_pool import MongoDBPool
from pirn.connectors.knots.database_query_source import DatabaseQuerySource
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

pool = MongoDBPool(config=MongoDBConfig(
    uri="mongodb://user:pass@mongo:27017",
    database="app",
    collection="events",
))

with Tapestry() as t:
    docs = DatabaseQuerySource(
        pool=pool,
        query='{"status": "pending"}',   # MQL filter dict as JSON string
        _config=KnotConfig(id="read"),
    )
    ProcessKnot(data=docs, _config=KnotConfig(id="process"))

result = await t.run(RunRequest())
await pool.close()
```

---

## Anti-patterns

**Passing a relational SQL query to a document pool** — document stores do not speak SQL (except CosmosDB's SQL API). Pass the native query format: MQL JSON for MongoDB, AQL string for ArangoDB, Mango selector JSON for CouchDB.

**Treating document pools as relational pools for schema-enforcing writes** — document stores are schema-flexible. The execute sink inserts/updates documents as-is. Validate schema in an upstream knot if enforcement is required.

---

## Constraints and gotchas

- **Each pool requires its own extra:** `pirn[mongodb]`, `pirn[arangodb]`, `pirn[couchdb]`, `pirn[couchbase]`, `pirn[cosmosdb]`, `pirn[firestore]`.
- **`MongoDBPool` uses motor** — the async MongoDB driver. Connection string follows the standard MongoDB URI format.
- **`FirestorePool` uses the native Firestore query DSL**, not MQL or SQL. The `query=` string is parsed by the pool into a Firestore query object.
- **`CosmosDBPool` supports the Cosmos DB SQL API** — a SQL-like query language. Use standard `SELECT` syntax.
- **`CouchbasePool` requires the Couchbase Server 7+ N1QL / SQL++ dialect** for `DatabaseQuerySource`.

---

## Quick reference

| Database | Config | Pool | Extra |
|----------|--------|------|-------|
| MongoDB | `MongoDBConfig` | `MongoDBPool` | `pirn[mongodb]` |
| ArangoDB | `ArangoDBConfig` | `ArangoDBPool` | `pirn[arangodb]` |
| CouchDB | `CouchDBConfig` | `CouchDBPool` | `pirn[couchdb]` |
| Couchbase | `CouchbaseConfig` | `CouchbasePool` | `pirn[couchbase]` |
| CosmosDB | `CosmosDBConfig` | `CosmosDBPool` | `pirn[cosmosdb]` |
| Firestore | `FirestoreConfig` | `FirestorePool` | `pirn[firestore]` |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
