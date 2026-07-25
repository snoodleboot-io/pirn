"""``McpPromptAdapter`` — turn MCP prompt definitions into reusable templates.

The adapter lists a server's prompts and builds an
:class:`~pirn_agents.mcp.mcp_prompt_template.McpPromptTemplate` for any of them:
argument specs (and which are required) come from ``prompts/list`` while the
message bodies — with their ``{argument}`` placeholders — come from
``prompts/get``. The resulting template is rendered locally, so an agent can
reuse one server round-trip's definition across many parameterisations.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.mcp.mcp_prompt_template import McpPromptTemplate


class McpPromptAdapter:
    """Build reusable message templates from an MCP server's prompts."""

    def __init__(self, *, client: McpClient) -> None:
        """Bind the adapter to a live client.

        Args:
            client: The :class:`McpClient` whose session backs prompt access.

        Raises:
            TypeError: If ``client`` is not an :class:`McpClient`.
        """
        if not isinstance(client, McpClient):
            raise TypeError(
                f"McpPromptAdapter: client must be an McpClient, got {type(client).__name__}"
            )
        self._client: McpClient = client

    async def list_prompts(self) -> list[dict[str, Any]]:
        """Return the server's prompt descriptors."""
        return await self._client.list_prompts()

    async def build_template(self, name: str) -> McpPromptTemplate:
        """Build a reusable :class:`McpPromptTemplate` for prompt ``name``.

        Argument requiredness is taken from the ``prompts/list`` descriptor and
        the placeholder message bodies from ``prompts/get`` (fetched without
        substitution so the raw ``{argument}`` templates are preserved).

        Args:
            name: The prompt's server name.

        Raises:
            TypeError: If ``name`` is not a non-empty string.
            McpError: If the server does not advertise a prompt named ``name``.
        """
        if not isinstance(name, str) or not name:
            raise TypeError(
                f"McpPromptAdapter.build_template: name must be a non-empty string, got {name!r}"
            )
        descriptors = await self._client.list_prompts()
        spec = next((d for d in descriptors if d.get("name") == name), None)
        if spec is None:
            raise McpError(f"MCP server does not advertise a prompt named {name!r}")
        required = self._required_arguments(spec.get("arguments"))
        raw = await self._client.get_prompt(name)
        return McpPromptTemplate(
            name=name,
            description=spec.get("description", ""),
            required_arguments=required,
            message_templates=self._message_templates(raw),
        )

    def _required_arguments(self, arguments: Any) -> frozenset[str]:
        """Collect the names of arguments the prompt descriptor marks required."""
        if not isinstance(arguments, list):
            return frozenset()
        names = {
            argument["name"]
            for argument in arguments
            if isinstance(argument, Mapping) and argument.get("required") and argument.get("name")
        }
        return frozenset(names)

    def _message_templates(self, raw: Mapping[str, Any]) -> list[tuple[str, str]]:
        """Extract ordered ``(role, body)`` pairs from a ``prompts/get`` payload."""
        messages = raw.get("messages")
        if not isinstance(messages, list):
            return []
        templates: list[tuple[str, str]] = []
        for message in messages:
            if not isinstance(message, Mapping):
                continue
            role = message.get("role", "user")
            templates.append((role, self._content_text(message.get("content"))))
        return templates

    def _content_text(self, content: Any) -> str:
        """Return the text of an MCP message content block (dict, string, or list)."""
        if isinstance(content, str):
            return content
        if isinstance(content, Mapping):
            text = content.get("text")
            return text if isinstance(text, str) else ""
        if isinstance(content, list):
            return "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, Mapping) and isinstance(block.get("text"), str)
            )
        return ""
