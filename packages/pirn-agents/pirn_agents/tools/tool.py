"""Interface for invocable agent tools.

A :class:`Tool` is a single capability the agent can call during
planning: a database lookup, a web search, a calculator, a custom
function. Concrete tools inherit from :class:`Tool` and override the
``name``, ``description``, and ``parameters_schema`` properties along
with :meth:`invoke`.

The base also exposes optional **capability facets** as default-returning
members that concrete tools override to opt in — mirroring the default-no-op
override points on core ``Knot``/``Emitter``:

* :attr:`stateful` / :attr:`state` — tools that carry injected state across
  invocations (default: not stateful, no state).
* :attr:`permissions` / :meth:`requires_approval` — permission / scope
  metadata and the human-approval gate (default: inert/unrestricted).
* :attr:`streaming` / :meth:`stream` / :meth:`collect_stream` — tools that
  yield incremental output (default: not streaming; :meth:`stream` raises).
* :meth:`content_identity` — the declared configuration that, together with
  the tool's class, name, description and parameters schema, fully determines
  what the tool does (default: ``None``, meaning the tool is identity-keyed).

Pydantic treats tools as opaque (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`) and :meth:`_pirn_audit_dict`
stays the identity-keyed token. What changes per tool is the **content hash**
that lineage and replay compare (PIR-840): :meth:`__pirn_canonical__` returns
that identity token unless the tool opts in through :meth:`content_identity`.
An identity-keyed tool hashes differently in every process, so a recorded run
replayed elsewhere refuses rather than substituting (a safe false mismatch). An
opted-in tool hashes the same wherever its class and declared config match, so
its recorded calls replay across processes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.tools.tool_declaration import ToolDeclaration
from pirn_agents.tools.tool_permissions import ToolPermissions


class Tool(PirnOpaqueValue):
    """Interface every tool must satisfy."""

    def declaration(self) -> ToolDeclaration:
        """Return the provider-neutral declaration envelope for this tool.

        Derived from the three required members, so every concrete tool —
        including MCP-discovered and agent-backed ones — gets a typed
        declaration without restating the neutral key names.
        """
        return ToolDeclaration(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema,
        )

    @property
    def name(self) -> str:
        """Stable identifier the agent uses to address the tool."""
        raise NotImplementedError(f"{type(self).__name__} must implement name")

    @property
    def description(self) -> str:
        """Human-readable description shown to the LLM during planning."""
        raise NotImplementedError(f"{type(self).__name__} must implement description")

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """JSON Schema describing the tool's expected arguments."""
        raise NotImplementedError(f"{type(self).__name__} must implement parameters_schema")

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        """Execute the tool with ``arguments`` and return the raw result."""
        raise NotImplementedError(f"{type(self).__name__} must implement invoke()")

    @property
    def stateful(self) -> bool:
        """Whether this tool carries injected state across invocations (default False)."""
        return False

    @property
    def state(self) -> Any:
        """The injected state/resource object, or ``None`` (default None)."""
        return None

    @property
    def permissions(self) -> ToolPermissions:
        """Permission / scope metadata for this tool (default: inert/unrestricted)."""
        return ToolPermissions()

    @property
    def streaming(self) -> bool:
        """Whether this tool yields incremental output via :meth:`stream` (default False)."""
        return False

    def stream(self, arguments: Mapping[str, Any]) -> AsyncIterator[Any]:
        """Return an async iterator of partial results for ``arguments``.

        Default: raise :class:`TypeError` — a non-streaming tool has nothing to stream.
        """
        raise TypeError(f"tool {self.name!r} is not a streaming tool")

    def requires_approval(self) -> bool:
        """Whether invoking this tool requires human approval (from its permissions)."""
        return self.permissions.approval_required

    async def collect_stream(self, arguments: Mapping[str, Any]) -> list[Any]:
        """Drain this tool's stream for ``arguments`` into a list of chunks."""
        return [chunk async for chunk in self.stream(arguments)]

    def content_identity(self) -> Mapping[str, Any] | None:
        """Return the declared config that makes this tool content-identified, or ``None``.

        Default: ``None`` — the tool is identity-keyed, so its content hash is
        unique to this instance in this process and replay across processes
        refuses. That is the safe direction for any tool whose behaviour depends
        on state the hash cannot see (a live connection, a store, a client).

        Override to opt in, returning **every** constructor input that changes
        what the tool does, as JSON-friendly primitives. Never include a
        credential, token, or any value that might be one. Returning ``None``
        from an override (e.g. when a test double or custom client was injected)
        keeps that instance identity-keyed. A tool that opts in must also be
        covered by the per-argument gate in
        ``tests/tools/test_tool_identity_gate.py``.
        """
        return None

    def __pirn_canonical__(self) -> Any:
        """Return the form :func:`pirn.core.hashing.content_hash` hashes.

        When :meth:`content_identity` is ``None`` this is the identity token
        from :meth:`_pirn_audit_dict`, exactly the value hashed before PIR-840.
        Otherwise it is the tool's class, name, description, parameters schema
        and declared config — the class is included so two tools that declare
        the same triple but behave differently never hash equal.
        """
        config = self.content_identity()
        if config is None:
            return self._pirn_audit_dict()
        tool_type = type(self)
        return {
            "tool": f"{tool_type.__module__}.{tool_type.__qualname__}",
            "name": self.name,
            "description": self.description,
            "parameters_schema": self.parameters_schema,
            "config": config,
        }

    def _clear_credentials(self) -> None:
        """Drop any in-memory credential reference held by the tool.

        :class:`Tool` has no shared credential field, so the default
        implementation is a no-op. Concrete tools that hold a
        credential string (token, api key, secret) on a private
        attribute should override this method to null whichever
        credential field they hold (e.g. ``self._config = None`` or
        ``self._api_key = None``). Callers should invoke this after
        tearing down any live SDK / client so the credential becomes
        garbage-collectable as soon as the tool reference is dropped.
        Long-running processes that hold tool references benefit;
        default deployments are unaffected.
        """
        pass
