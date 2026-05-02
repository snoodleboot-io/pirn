"""Interface for invocable agent tools.

A :class:`Tool` is a single capability the agent can call during
planning: a database lookup, a web search, a calculator, a custom
function. Concrete tools inherit from :class:`Tool` and override the
``name``, ``description``, and ``parameters_schema`` properties along
with :meth:`invoke`.

Pydantic treats tools as opaque (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
identity-keyed serialiser keeps content-addressing cache stable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class Tool(PirnOpaqueValue):
    """Interface every tool must satisfy."""

    @property
    def name(self) -> str:
        """Stable identifier the agent uses to address the tool."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement name"
        )

    @property
    def description(self) -> str:
        """Human-readable description shown to the LLM during planning."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement description"
        )

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """JSON Schema describing the tool's expected arguments."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement parameters_schema"
        )

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        """Execute the tool with ``arguments`` and return the raw result."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement invoke()"
        )
