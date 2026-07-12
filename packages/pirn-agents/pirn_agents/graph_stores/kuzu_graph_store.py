"""``KuzuGraphStore`` — a Kuzu-backed :class:`GraphStore` (``[kuzu]`` extra).

Adapts the neutral graph contract onto the embedded Kuzu engine. All vendor
specifics live behind a
:class:`~pirn_agents.graph_stores.graph_backend_client.GraphBackendClient`: by
default the store lazily builds a
:class:`~pirn_agents.graph_stores.kuzu_backend_client.KuzuBackendClient` (which
imports ``kuzu`` behind the ``[kuzu]`` extra), but a client may be injected so
mirrored tests run the full conformance suite against an in-memory fake with no
backend installed. Importing this module pulls in no backend.
"""

from __future__ import annotations

from pirn_agents.graph_stores.backend_graph_store import BackendGraphStore
from pirn_agents.graph_stores.graph_backend_client import GraphBackendClient


class KuzuGraphStore(BackendGraphStore):
    """A Kuzu :class:`GraphStore` speaking the neutral backend client."""

    def __init__(
        self,
        *,
        db_path: str = ":memory:",
        client: GraphBackendClient | None = None,
    ) -> None:
        """Initialise the Kuzu adapter.

        Args:
            db_path: Filesystem path for the embedded database, or ``":memory:"``
                for an ephemeral in-process instance.
            client: Optional pre-built neutral backend client (the test seam);
                when supplied no backend import happens.
        """
        super().__init__(client=client)
        self._db_path: str = db_path

    async def _create_client(self) -> GraphBackendClient:
        """Lazily build the real Kuzu backend client (imports ``kuzu``)."""
        from pirn_agents.graph_stores.kuzu_backend_client import KuzuBackendClient

        return KuzuBackendClient(db_path=self._db_path)
