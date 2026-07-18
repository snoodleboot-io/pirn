"""``Neo4jBackendClient`` — the real Neo4j wrapper behind the neutral graph client.

Implements
:class:`~pirn_agents.graph_stores.graph_backend_client.GraphBackendClient` by
lazily importing ``neo4j`` (the ``[neo4j]`` extra) and translating the neutral
node/edge/neighbor mappings into parameterised Cypher. Importing this module
pulls in no backend — the driver is imported only when a method actually runs,
which happens under the ``needs_neo4j`` conformance run.

To stay provider-neutral and avoid unsafe dynamic label injection, every node is
stored under a single ``:Node`` label carrying ``id`` / ``type`` properties, and
every relationship under a single ``:REL`` type carrying an ``id`` / ``type``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents._require import _require
from pirn_agents.credential_ref import CredentialRef
from pirn_agents.graph_stores.graph_backend_client import GraphBackendClient


class Neo4jBackendClient(GraphBackendClient):
    """Neutral-client wrapper over an async Neo4j driver."""

    def __init__(
        self,
        *,
        uri: str,
        database: str | None = None,
        username: str | None = None,
        credential: CredentialRef | None = None,
    ) -> None:
        """Initialise the wrapper without importing the backend.

        Args:
            uri: The Neo4j connection URI (e.g. ``"bolt://localhost:7687"``).
            database: Optional target database name.
            username: Optional username for basic auth.
            credential: Optional password credential for basic auth.
        """
        self._uri: str = uri
        self._database: str | None = database
        self._username: str | None = username
        self._credential: CredentialRef | None = credential
        self._driver: Any | None = None

    async def _get_driver(self) -> Any:
        """Build the async driver once, lazily importing ``neo4j``."""
        if self._driver is None:
            neo4j = _require("neo4j", "neo4j")
            auth = None
            if self._username is not None and self._credential is not None:
                auth = (self._username, self._credential.reveal())
            self._driver = neo4j.AsyncGraphDatabase.driver(self._uri, auth=auth)
        return self._driver

    async def _run(self, cypher: str, params: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        """Run ``cypher`` with ``params`` and return the records as dicts."""
        driver = await self._get_driver()
        async with driver.session(database=self._database) as session:
            result = await session.run(cypher, dict(params))
            records = [record.data() async for record in result]
        return records

    async def upsert_nodes(self, nodes: Sequence[Mapping[str, Any]]) -> None:
        """MERGE each node by id, setting its type and properties."""
        await self._run(
            "UNWIND $rows AS row "
            "MERGE (n:Node {id: row.id}) "
            "SET n.type = row.type, n += row.properties",
            {"rows": [dict(node) for node in nodes]},
        )

    async def upsert_edges(self, edges: Sequence[Mapping[str, Any]]) -> None:
        """MERGE each relationship by id between its endpoint nodes."""
        await self._run(
            "UNWIND $rows AS row "
            "MATCH (s:Node {id: row.source_id}), (t:Node {id: row.target_id}) "
            "MERGE (s)-[r:REL {id: row.id}]->(t) "
            "SET r.type = row.type, r += row.properties",
            {"rows": [dict(edge) for edge in edges]},
        )

    async def get_node(self, node_id: str) -> Mapping[str, Any] | None:
        """Return the node mapping stored under ``node_id``, or ``None``."""
        records = await self._run(
            "MATCH (n:Node {id: $id}) RETURN properties(n) AS props", {"id": node_id}
        )
        if not records:
            return None
        return self._node_from_props(records[0]["props"])

    async def get_edge(self, edge_id: str) -> Mapping[str, Any] | None:
        """Return the edge mapping stored under ``edge_id``, or ``None``."""
        records = await self._run(
            "MATCH (s:Node)-[r:REL {id: $id}]->(t:Node) "
            "RETURN properties(r) AS props, s.id AS source_id, t.id AS target_id",
            {"id": edge_id},
        )
        if not records:
            return None
        return self._edge_from_record(records[0])

    async def neighbors(
        self,
        node_id: str,
        *,
        direction: str,
        edge_types: Sequence[str] | None,
        limit: int | None,
    ) -> list[Mapping[str, Any]]:
        """Return the one-hop neighbor mappings of ``node_id``."""
        arrow = {"out": "-[r:REL]->", "in": "<-[r:REL]-", "both": "-[r:REL]-"}[direction]
        where = "" if edge_types is None else "WHERE r.type IN $types "
        tail = "" if limit is None else "LIMIT $limit"
        cypher = (
            f"MATCH (n:Node {{id: $id}}){arrow}(m:Node) "
            f"{where}"
            "RETURN properties(r) AS edge_props, startNode(r).id AS source_id, "
            "endNode(r).id AS target_id, properties(m) AS node_props "
            f"{tail}"
        )
        params: dict[str, Any] = {"id": node_id}
        if edge_types is not None:
            params["types"] = list(edge_types)
        if limit is not None:
            params["limit"] = limit
        records = await self._run(cypher, params)
        return [
            {
                "edge": self._edge_from_record(
                    {
                        "props": record["edge_props"],
                        "source_id": record["source_id"],
                        "target_id": record["target_id"],
                    }
                ),
                "node": self._node_from_props(record["node_props"]),
            }
            for record in records
        ]

    async def query_nodes(
        self,
        *,
        node_type: str | None,
        properties: Mapping[str, Any] | None,
        limit: int | None,
    ) -> list[Mapping[str, Any]]:
        """Return node mappings matching ``node_type`` and every ``properties`` entry."""
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if node_type is not None:
            clauses.append("n.type = $node_type")
            params["node_type"] = node_type
        if properties is not None:
            for i, (key, value) in enumerate(properties.items()):
                clauses.append(f"n[$key_{i}] = $val_{i}")
                params[f"key_{i}"] = key
                params[f"val_{i}"] = value
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        tail = "" if limit is None else "LIMIT $limit"
        if limit is not None:
            params["limit"] = limit
        records = await self._run(
            f"MATCH (n:Node) {where}RETURN properties(n) AS props {tail}", params
        )
        return [self._node_from_props(record["props"]) for record in records]

    async def delete_nodes(self, ids: Sequence[str]) -> None:
        """Detach-delete every node in ``ids`` (removing incident edges)."""
        await self._run(
            "UNWIND $ids AS nid MATCH (n:Node {id: nid}) DETACH DELETE n", {"ids": list(ids)}
        )

    async def delete_edges(self, ids: Sequence[str]) -> None:
        """Delete every relationship in ``ids``."""
        await self._run(
            "UNWIND $ids AS eid MATCH ()-[r:REL {id: eid}]->() DELETE r", {"ids": list(ids)}
        )

    async def close(self) -> None:
        """Close the async driver if one was built."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
        self._credential = None

    @staticmethod
    def _node_from_props(props: Mapping[str, Any]) -> Mapping[str, Any]:
        """Split a stored node's flat property map into the neutral node shape."""
        rest = {k: v for k, v in props.items() if k not in ("id", "type")}
        return {"id": props["id"], "type": props["type"], "properties": rest}

    @staticmethod
    def _edge_from_record(record: Mapping[str, Any]) -> Mapping[str, Any]:
        """Build the neutral edge shape from a relationship record."""
        props = record["props"]
        rest = {k: v for k, v in props.items() if k not in ("id", "type")}
        return {
            "id": props["id"],
            "source_id": record["source_id"],
            "target_id": record["target_id"],
            "type": props["type"],
            "properties": rest,
        }
