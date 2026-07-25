"""``McpPromptTemplate`` — a reusable message template built from an MCP prompt.

An MCP prompt definition (a name, an argument spec, and one or more message
bodies containing ``{argument}`` placeholders) is captured here once and rendered
many times via :meth:`render`, which substitutes arguments and returns F1
:class:`~pirn_agents.types.agent_message.AgentMessage`\\ s. Arguments are
validated with ``isinstance`` (every value must be a string) and required
arguments must be supplied, so a bad call fails loudly instead of emitting a
half-substituted prompt.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pirn_agents.types.agent_message import AgentMessage


class McpPromptTemplate:
    """A parameterised, reusable prompt rendered into agent messages."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        required_arguments: frozenset[str],
        message_templates: Sequence[tuple[str, str]],
    ) -> None:
        """Capture a prompt's identity, required args, and message bodies.

        Args:
            name: The prompt's stable server name.
            description: Human-readable description of the prompt.
            required_arguments: Names of arguments the server marks required.
            message_templates: Ordered ``(role, body)`` pairs whose ``body`` may
                contain ``{argument}`` placeholders.

        Raises:
            TypeError: If ``name`` is not a non-empty string.
        """
        if not isinstance(name, str) or not name:
            raise TypeError(f"McpPromptTemplate: name must be a non-empty string, got {name!r}")
        self._name: str = name
        self._description: str = description
        self._required_arguments: frozenset[str] = frozenset(required_arguments)
        self._message_templates: tuple[tuple[str, str], ...] = tuple(message_templates)

    @property
    def name(self) -> str:
        """Return the prompt's stable name."""
        return self._name

    @property
    def description(self) -> str:
        """Return the prompt's description."""
        return self._description

    @property
    def required_arguments(self) -> frozenset[str]:
        """Return the set of argument names the server marks required."""
        return self._required_arguments

    def render(self, arguments: Mapping[str, str] | None = None) -> list[AgentMessage]:
        """Substitute ``arguments`` into every message body and return messages.

        Args:
            arguments: Mapping of argument name to string value. May be ``None``
                when the prompt has no required arguments.

        Returns:
            One :class:`AgentMessage` per template body, in template order, with
            each ``{name}`` placeholder replaced by its argument value.

        Raises:
            TypeError: If ``arguments`` is not a Mapping, or any value is not a
                string.
            ValueError: If a required argument is missing.
        """
        provided: Mapping[str, str] = arguments if arguments is not None else {}
        if not isinstance(provided, Mapping):
            raise TypeError(
                f"McpPromptTemplate.render: arguments must be a Mapping or None, "
                f"got {type(provided).__name__}"
            )
        for key, value in provided.items():
            if not isinstance(value, str):
                raise TypeError(
                    f"McpPromptTemplate.render: argument {key!r} must be a string, "
                    f"got {type(value).__name__}"
                )
        missing = self._required_arguments - set(provided)
        if missing:
            raise ValueError(
                f"McpPromptTemplate.render: missing required argument(s): {sorted(missing)}"
            )
        return [
            AgentMessage(role=role, content=_substitute(body, provided), name=self._name)
            for role, body in self._message_templates
        ]


def _substitute(body: str, arguments: Mapping[str, str]) -> str:
    """Replace each ``{name}`` token in ``body`` with its argument value.

    A plain token replace (not ``str.format``) is used so literal braces in the
    body — e.g. an embedded JSON example — are left untouched.
    """
    rendered = body
    for name, value in arguments.items():
        rendered = rendered.replace("{" + name + "}", value)
    return rendered
