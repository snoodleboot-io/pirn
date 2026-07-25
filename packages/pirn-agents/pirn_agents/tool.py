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

Pydantic treats tools as opaque (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
identity-keyed serialiser keeps content-addressing cache stable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.tool_permissions import ToolPermissions


class Tool(PirnOpaqueValue):
    """Interface every tool must satisfy."""

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
