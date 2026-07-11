"""``Neo4jGraphStore`` — a Neo4j-backed :class:`GraphStore` (``[neo4j]`` extra).

Adapts the neutral graph contract onto Neo4j. All vendor specifics live behind a
:class:`~pirn_agents.graph_stores.graph_backend_client.GraphBackendClient`: by
default the store lazily builds a
:class:`~pirn_agents.graph_stores.neo4j_backend_client.Neo4jBackendClient` (which
imports ``neo4j`` behind the ``[neo4j]`` extra), but a client may be injected so
mirrored tests run the full conformance suite against an in-memory fake with no
backend installed. Importing this module pulls in no backend.
"""

from __future__ import annotations

from pirn_agents.credential_ref import CredentialRef
from pirn_agents.graph_stores.backend_graph_store import BackendGraphStore
from pirn_agents.graph_stores.graph_backend_client import GraphBackendClient


class Neo4jGraphStore(BackendGraphStore):
    """A Neo4j :class:`GraphStore` speaking the neutral backend client."""

    def __init__(
        self,
        *,
        uri: str = "bolt://localhost:7687",
        database: str | None = None,
        username: str | None = None,
        credential: CredentialRef | None = None,
        client: GraphBackendClient | None = None,
    ) -> None:
        """Initialise the Neo4j adapter.

        Args:
            uri: Neo4j connection URI used when building a real client.
            database: Optional target database name.
            username: Optional username for basic auth.
            credential: Optional password credential scrubbed on :meth:`close`.
            client: Optional pre-built neutral backend client (the test seam);
                when supplied no backend import happens.
        """
        super().__init__(credential=credential, client=client)
        self._uri: str = uri
        self._database: str | None = database
        self._username: str | None = username

    async def _create_client(self) -> GraphBackendClient:
        """Lazily build the real Neo4j backend client (imports ``neo4j``)."""
        from pirn_agents.graph_stores.neo4j_backend_client import Neo4jBackendClient

        return Neo4jBackendClient(
            uri=self._uri,
            database=self._database,
            username=self._username,
            credential=self._credential,
        )
