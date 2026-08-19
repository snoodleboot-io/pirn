"""``AgentReferences`` — bind the labels in an :class:`AgentSpec` to live objects.

A spec is data: it names its LLM provider, memory store, tools and components by
*reference label* (``llm: my-llm``), because an open HTTP client and a live
vector store cannot be written to a YAML file. Something has to map those labels
back to real objects before an agent can run, and that something is the caller —
it owns the connections.

This class is that mapping, and the missing half of the round trip
(PIR-732). Before it, :meth:`AgentBuilder.to_spec` could serialise a
configuration and :class:`~pirn_agents.builder.agent_spec_loader.AgentSpecLoader`
could parse one back, but nothing could *build* from one: the declarative
surface could describe an agent it had no way to run.

    references = (
        AgentReferences()
        .register("my-llm", llm_provider)
        .register("kb", memory_store)
    )
    spec = AgentSpecLoader.from_yaml(text)
    with Tapestry() as t:
        agent = Agent.from_spec(spec, references=references).input("hi").build()

Resolution is strict: an unknown label raises rather than yielding ``None``, so
a typo in a config file is a loud failure at bind time instead of a knot wired
to nothing.

References:
    - :class:`pirn_agents.builder.agent_spec.AgentSpec`
    - :meth:`pirn_agents.builder.agent_builder.AgentBuilder.from_spec`
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pirn_agents.tools.tool import Tool


class AgentReferences:
    """A caller-owned table mapping spec reference labels to live objects."""

    def __init__(self, initial: Mapping[str, Any] | None = None) -> None:
        """Start a table, optionally seeded from a mapping.

        Args:
            initial: Label-to-object pairs to register up front.

        Raises:
            TypeError: If ``initial`` is not a mapping.
        """
        if initial is not None and not isinstance(initial, Mapping):
            raise TypeError(
                f"AgentReferences: initial must be a mapping, got {type(initial).__name__}"
            )
        self._objects: dict[str, Any] = {}
        for label, value in (initial or {}).items():
            self.register(label, value)

    def register(self, label: str, value: Any) -> AgentReferences:
        """Bind one label to one live object; return ``self`` for chaining.

        Args:
            label: The reference as it appears in a spec.
            value: The live object it stands for.

        Raises:
            TypeError: If ``label`` is not a string.
            ValueError: If ``label`` is empty.
        """
        if not isinstance(label, str):
            raise TypeError(
                f"AgentReferences.register: label must be a str, got {type(label).__name__}"
            )
        if not label:
            raise ValueError("AgentReferences.register: label must be a non-empty string")
        self._objects[label] = value
        return self

    def register_tools(self, tools: Iterable[Tool]) -> AgentReferences:
        """Bind each tool under its own ``name``; return ``self`` for chaining.

        Tools are the one kind of component a spec labels by an intrinsic
        identity rather than a caller-chosen one — ``AgentBuilder.to_spec``
        writes ``tool.name`` — so registering them needs no naming decision.

        Raises:
            TypeError: If any element is not a :class:`Tool`.
        """
        for index, tool in enumerate(tools):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"AgentReferences.register_tools: tools[{index}] must be a Tool, "
                    f"got {type(tool).__name__}"
                )
            self.register(tool.name, tool)
        return self

    def resolve(self, label: str) -> Any:
        """Return the live object bound to ``label``.

        Raises:
            KeyError: If ``label`` is not registered. The message lists what is,
                because the usual cause is a typo in a hand-written config.
        """
        if label not in self._objects:
            raise KeyError(
                f"AgentReferences: unknown reference {label!r}; "
                f"registered references are {list(self.labels())!r}"
            )
        return self._objects[label]

    def labels(self) -> tuple[str, ...]:
        """Return the registered labels, sorted."""
        return tuple(sorted(self._objects))

    def __contains__(self, label: object) -> bool:
        """Return whether ``label`` is registered."""
        return label in self._objects
