"""``McpResourceAdapter`` — surface MCP resources for agent context injection.

MCP resources are read-only context (files, records, docs). This adapter lists
and reads them through the client and shapes their content two ways for the F1
context path:

* :meth:`as_context_messages` yields system-role
  :class:`~pirn_agents.types.agent_message.AgentMessage`\\ s ready to prepend at
  :class:`~pirn_agents.input.context_builder.ContextBuilder` time; and
* :meth:`inject_into_store` writes each resource into a
  :class:`~pirn_agents.memory_store.MemoryStore` so a
  :class:`~pirn_agents.memory.memory_retriever.MemoryRetriever` can fetch it.

Resource payloads are validated with ``isinstance`` so a malformed server
response fails loudly rather than injecting garbage.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.memory_store import MemoryStore
from pirn_agents.types.agent_message import AgentMessage


class McpResourceAdapter:
    """Adapt MCP resources into injectable agent context."""

    def __init__(self, *, client: McpClient) -> None:
        """Bind the adapter to a live client.

        Args:
            client: The :class:`McpClient` whose session backs resource access.

        Raises:
            TypeError: If ``client`` is not an :class:`McpClient`.
        """
        if not isinstance(client, McpClient):
            raise TypeError(
                f"McpResourceAdapter: client must be an McpClient, got {type(client).__name__}"
            )
        self._client: McpClient = client

    async def list_resources(self) -> list[dict[str, Any]]:
        """Return the server's resource descriptors."""
        return await self._client.list_resources()

    async def read_text(self, uri: str) -> str:
        """Read resource ``uri`` and return its concatenated text content.

        Raises:
            TypeError: If ``uri`` is not a non-empty string.
            McpError: If the resource payload is malformed (``contents`` is not a
                list, or an entry is not a mapping).
        """
        if not isinstance(uri, str) or not uri:
            raise TypeError(
                f"McpResourceAdapter.read_text: uri must be a non-empty string, got {uri!r}"
            )
        raw = await self._client.read_resource(uri)
        return _resource_to_text(uri, raw)

    async def as_context_messages(
        self,
        *,
        uris: Sequence[str] | None = None,
        role: str = "system",
    ) -> list[AgentMessage]:
        """Read resources and return them as messages for context injection.

        Args:
            uris: Explicit resource URIs to inject; when ``None`` every resource
                the server lists is injected.
            role: Role stamped on each produced message (defaults ``"system"``).

        Returns:
            One :class:`AgentMessage` per resource, in ``uris`` order (or server
            order when discovering). Resources with no text content are skipped.

        Raises:
            TypeError: If ``role`` is not a non-empty string.
        """
        if not isinstance(role, str) or not role:
            raise TypeError(
                f"McpResourceAdapter.as_context_messages: role must be a non-empty string, "
                f"got {role!r}"
            )
        selected = await self._resolve_uris(uris)
        messages: list[AgentMessage] = []
        for uri in selected:
            text = await self.read_text(uri)
            if text:
                messages.append(AgentMessage(role=role, content=text, name=uri))
        return messages

    async def inject_into_store(
        self,
        store: MemoryStore,
        *,
        uris: Sequence[str] | None = None,
        key_prefix: str = "mcp:resource:",
    ) -> list[str]:
        """Read resources and persist each into ``store`` keyed by URI.

        Args:
            store: Destination :class:`MemoryStore`.
            uris: Explicit URIs to inject; when ``None`` every listed resource.
            key_prefix: Prefix prepended to each URI to form its store key.

        Returns:
            The list of keys written, in injection order.

        Raises:
            TypeError: If ``store`` is not a :class:`MemoryStore`.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"McpResourceAdapter.inject_into_store: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        selected = await self._resolve_uris(uris)
        keys: list[str] = []
        for uri in selected:
            text = await self.read_text(uri)
            key = f"{key_prefix}{uri}"
            await store.store(key, {"uri": uri, "content": text})
            keys.append(key)
        return keys

    async def _resolve_uris(self, uris: Sequence[str] | None) -> list[str]:
        """Return the explicit ``uris`` or discover every resource URI."""
        if uris is not None:
            return list(uris)
        descriptors = await self.list_resources()
        return [descriptor["uri"] for descriptor in descriptors if descriptor.get("uri")]


def _resource_to_text(uri: str, raw: Mapping[str, Any]) -> str:
    """Extract and join the text blocks of an MCP ``resources/read`` payload.

    Binary (``blob``) entries are skipped — they are not injectable as text — but
    a structurally malformed payload raises :class:`McpError`.
    """
    contents = raw.get("contents")
    if not isinstance(contents, list):
        raise McpError(f"MCP resource {uri!r} returned malformed contents: {contents!r}")
    parts: list[str] = []
    for entry in contents:
        if not isinstance(entry, Mapping):
            raise McpError(f"MCP resource {uri!r} has a non-mapping content entry: {entry!r}")
        text = entry.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)
