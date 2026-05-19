`pirn.domains.connectors.graph` provides `ConnectionConfig` and connection pool implementations for Neo4j, Memgraph, and OrientDB — it does not execute queries; pass the pool to `DatabaseQuerySource` / `DatabaseExecuteSink` with Cypher or OrientDB SQL query strings.

---

## Mental model

Each graph database has a `*Config` (URI, credentials) and a `*Pool` (`DatabaseConnectionPool` subclass). Pass the pool to knots. Graph query syntax is vendor-specific: Neo4j and Memgraph use Cypher, OrientDB uses its extended SQL dialect with graph traversal extensions.

---

## Source map

```
pirn/domains/connectors/graph/
├── neo4j_config.py      Neo4jConfig      — uri (bolt://...), user, password, database
├── neo4j_pool.py        Neo4jPool        — neo4j async driver (bolt protocol)
├── memgraph_config.py   MemgraphConfig   — host, port, user, password, encrypted
├── memgraph_pool.py     MemgraphPool     — GQLAlchemy async client (Bolt-compatible)
├── orientdb_config.py   OrientdbConfig   — host, port, database, user, password
└── orientdb_pool.py     OrientdbPool     — pyorient async wrapper
```

---

## Canonical pattern

### Neo4j — query with Cypher

```python
from pirn.domains.connectors.graph.neo4j_config import Neo4jConfig
from pirn.domains.connectors.graph.neo4j_pool import Neo4jPool
from pirn.domains.connectors.knots.database_query_source import DatabaseQuerySource
from pirn import Tapestry, KnotConfig, RunRequest

pool = Neo4jPool(config=Neo4jConfig(
    uri="bolt://neo4j:7687", user="neo4j", password=os.environ["NEO4J_PASS"]
))

with Tapestry() as t:
    nodes = DatabaseQuerySource(
        pool=pool,
        query="MATCH (n:Person)-[:KNOWS]->(m) RETURN n.name, m.name LIMIT 100",
        _config=KnotConfig(id="graph"),
    )
    ProcessKnot(data=nodes, _config=KnotConfig(id="process"))

result = await t.run(RunRequest())
await pool.close()
```

---

## Constraints and gotchas

- **Each pool requires its own extra:** `pirn[neo4j]`, `pirn[memgraph]`, `pirn[orientdb]`.
- **`MemgraphPool` is Bolt-compatible** with Neo4j — the same Cypher queries work on both. Use `MemgraphPool` when targeting Memgraph specifically for its streaming/in-memory properties.
- **`Neo4jPool` requires the Bolt port (default 7687)**, not the HTTP browser port (7474).
- **`OrientdbPool` is legacy.** OrientDB SQL is not standard SQL — graph traversal uses `TRAVERSE` and `MATCH` extensions.

---

## Quick reference

| Database | Config | Pool | Query language | Extra |
|----------|--------|------|----------------|-------|
| Neo4j | `Neo4jConfig` | `Neo4jPool` | Cypher | `pirn[neo4j]` |
| Memgraph | `MemgraphConfig` | `MemgraphPool` | Cypher | `pirn[memgraph]` |
| OrientDB | `OrientdbConfig` | `OrientdbPool` | OrientDB SQL + graph extensions | `pirn[orientdb]` |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
