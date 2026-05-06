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
