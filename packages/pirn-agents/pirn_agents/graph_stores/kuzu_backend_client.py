"""``KuzuBackendClient`` — the real Kuzu wrapper behind the neutral graph client.

Implements
:class:`~pirn_agents.graph_stores.graph_backend_client.GraphBackendClient` by
lazily importing ``kuzu`` (the ``[kuzu]`` extra) and translating the neutral
node/edge/neighbor mappings onto Kuzu's embedded property graph. Importing this
module pulls in no backend — the driver is imported only when a method actually
runs, which happens under the ``needs_kuzu`` conformance run.

Kuzu is an embedded, schema-first engine with a synchronous driver, so this
wrapper (a) provisions a generic ``Node`` / ``Rel`` schema on first use, storing
arbitrary node/edge ``properties`` as a JSON string column for provider
neutrality, and (b) offloads the blocking driver calls to a worker thread via
:func:`asyncio.to_thread` so the neutral surface stays ``async``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents._require import _require


class KuzuBackendClient:
    """Neutral-client wrapper over an embedded Kuzu connection."""

    def __init__(self, *, db_path: str = ":memory:") -> None:
        """Initialise the wrapper without importing the backend.

        Args:
            db_path: Filesystem path for the embedded database, or ``":memory:"``
                for an ephemeral in-process instance.
        """
        self._db_path: str = db_path
        self._connection: Any | None = None

    def _connect(self) -> Any:
        """Build the connection and provision the generic schema once (sync)."""
        if self._connection is None:
            kuzu = _require("kuzu", "kuzu")
            database = kuzu.Database(self._db_path)
            connection = kuzu.Connection(database)
            connection.execute(
                "CREATE NODE TABLE IF NOT EXISTS Node("
                "id STRING, type STRING, props STRING, PRIMARY KEY(id))"
            )
            connection.execute(
                "CREATE REL TABLE IF NOT EXISTS Rel("
                "FROM Node TO Node, id STRING, type STRING, props STRING)"
            )
            self._connection = connection
        return self._connection

    def _execute(self, cypher: str, params: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Run ``cypher`` with ``params`` and return the rows as dicts (sync)."""
        connection = self._connect()
        result = connection.execute(cypher, parameters=dict(params))
        rows: list[dict[str, Any]] = []
        while result.has_next():
            rows.append(dict(result.get_next_as_dict()))
        return rows

    async def _run(self, cypher: str, params: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Run ``cypher`` on a worker thread so the surface stays async."""
        return await asyncio.to_thread(self._execute, cypher, dict(params))

    async def upsert_nodes(self, nodes: Sequence[Mapping[str, Any]]) -> None:
        """MERGE each node by id, storing type and JSON-encoded properties."""
        for node in nodes:
            await self._run(
                "MERGE (n:Node {id: $id}) SET n.type = $type, n.props = $props",
                {
                    "id": node["id"],
                    "type": node["type"],
                    "props": json.dumps(dict(node.get("properties", {}))),
                },
            )

    async def upsert_edges(self, edges: Sequence[Mapping[str, Any]]) -> None:
        """MERGE each relationship by id between its endpoint nodes."""
        for edge in edges:
            await self._run(
                "MATCH (s:Node {id: $source_id}), (t:Node {id: $target_id}) "
                "MERGE (s)-[r:Rel {id: $id}]->(t) SET r.type = $type, r.props = $props",
                {
                    "id": edge["id"],
                    "source_id": edge["source_id"],
                    "target_id": edge["target_id"],
                    "type": edge["type"],
                    "props": json.dumps(dict(edge.get("properties", {}))),
                },
            )

    async def get_node(self, node_id: str) -> Mapping[str, Any] | None:
        """Return the node mapping stored under ``node_id``, or ``None``."""
        rows = await self._run(
            "MATCH (n:Node {id: $id}) RETURN n.id AS id, n.type AS type, n.props AS props",
            {"id": node_id},
        )
        return self._node_from_row(rows[0]) if rows else None

    async def get_edge(self, edge_id: str) -> Mapping[str, Any] | None:
        """Return the edge mapping stored under ``edge_id``, or ``None``."""
        rows = await self._run(
            "MATCH (s:Node)-[r:Rel {id: $id}]->(t:Node) "
            "RETURN r.id AS id, r.type AS type, r.props AS props, "
            "s.id AS source_id, t.id AS target_id",
            {"id": edge_id},
        )
        return self._edge_from_row(rows[0]) if rows else None

    async def neighbors(
        self,
        node_id: str,
        *,
        direction: str,
        edge_types: Sequence[str] | None,
        limit: int | None,
    ) -> list[Mapping[str, Any]]:
        """Return the one-hop neighbor mappings of ``node_id``."""
        arrow = {"out": "-[r:Rel]->", "in": "<-[r:Rel]-", "both": "-[r:Rel]-"}[direction]
        where = "" if edge_types is None else "WHERE r.type IN $types "
        tail = "" if limit is None else "LIMIT $limit"
        cypher = (
            f"MATCH (n:Node {{id: $id}}){arrow}(m:Node) {where}"
            "RETURN r.id AS id, r.type AS type, r.props AS props, "
            "n.id AS n_id, m.id AS m_id, m.type AS m_type, m.props AS m_props, "
            f"startNode(r).id AS source_id, endNode(r).id AS target_id {tail}"
        )
        params: dict[str, Any] = {"id": node_id}
        if edge_types is not None:
            params["types"] = list(edge_types)
        if limit is not None:
            params["limit"] = limit
        rows = await self._run(cypher, params)
        return [
            {
                "edge": self._edge_from_row(row),
                "node": {
                    "id": row["m_id"],
                    "type": row["m_type"],
                    "properties": json.loads(row["m_props"] or "{}"),
                },
            }
            for row in rows
        ]

    async def query_nodes(
        self,
        *,
        node_type: str | None,
        properties: Mapping[str, Any] | None,
        limit: int | None,
    ) -> list[Mapping[str, Any]]:
        """Return node mappings matching ``node_type`` and every ``properties`` entry.

        The property equality filter is applied in Python after fetching, since
        properties are stored as an opaque JSON column.
        """
        where = "" if node_type is None else "WHERE n.type = $node_type "
        params: dict[str, Any] = {}
        if node_type is not None:
            params["node_type"] = node_type
        rows = await self._run(
            f"MATCH (n:Node) {where}RETURN n.id AS id, n.type AS type, n.props AS props", params
        )
        out: list[Mapping[str, Any]] = []
        for row in rows:
            node = self._node_from_row(row)
            if properties is not None and not all(
                node["properties"].get(key) == value for key, value in properties.items()
            ):
                continue
            out.append(node)
            if limit is not None and len(out) >= limit:
                break
        return out

    async def delete_nodes(self, ids: Sequence[str]) -> None:
        """Detach-delete every node in ``ids`` (removing incident edges)."""
        for node_id in ids:
            await self._run("MATCH (n:Node {id: $id}) DETACH DELETE n", {"id": node_id})

    async def delete_edges(self, ids: Sequence[str]) -> None:
        """Delete every relationship in ``ids``."""
        for edge_id in ids:
            await self._run("MATCH ()-[r:Rel {id: $id}]->() DELETE r", {"id": edge_id})

    async def close(self) -> None:
        """Drop the connection reference (Kuzu closes with the process)."""
        self._connection = None

    @staticmethod
    def _node_from_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
        """Build the neutral node shape from a Kuzu row (JSON props decoded)."""
        return {
            "id": row["id"],
            "type": row["type"],
            "properties": json.loads(row["props"] or "{}"),
        }

    @staticmethod
    def _edge_from_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
        """Build the neutral edge shape from a Kuzu row (JSON props decoded)."""
        return {
            "id": row["id"],
            "source_id": row["source_id"],
            "target_id": row["target_id"],
            "type": row["type"],
            "properties": json.loads(row["props"] or "{}"),
        }
