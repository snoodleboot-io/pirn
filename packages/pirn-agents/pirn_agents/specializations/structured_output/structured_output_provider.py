"""``StructuredOutputProvider`` — the provider seam the native strategies use.

A ``runtime_checkable`` :class:`typing.Protocol` describing the small surface a
provider must expose for the F20 native structured-output paths. It is a strict
superset of the plain :class:`pirn.core.providers.llm_provider.LLMProvider`
contract: capability advertisement plus a single structured chat call and three
request-option shapers, one per native mechanism.

Keeping this a structural protocol lets the unified decoder (S4) probe *any*
provider with :func:`isinstance` and degrade gracefully — a plain
``LLMProvider`` that does not implement these members simply routes to the
extract-validate-retry fallback. Every vendor-specific wire shape stays behind
the provider's own override of the option shapers, so no strategy embeds a
provider-specific code path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.toolset import Toolset
from pirn_agents.types.agent_response import AgentResponse


@runtime_checkable
class StructuredOutputProvider(Protocol):
    """Structural provider contract for native structured-output decoding."""

    def structured_output_capability(self) -> StructuredOutputCapability:
        """Return the provider's advertised native structured-output flags."""
        ...

    async def structured_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tools: Toolset | None = None,
        request_options: Mapping[str, Any] | None = None,
    ) -> AgentResponse:
        """Send a chat completion merging ``request_options`` into the request."""
        ...

    def native_schema_option(self, schema: Mapping[str, Any], *, name: str) -> Mapping[str, Any]:
        """Return request options carrying a native schema/``response_format``."""
        ...

    def forced_tool_choice_option(self, tool_name: str) -> Mapping[str, Any]:
        """Return request options forcing a single named tool call."""
        ...

    def constrained_decoding_option(self, constraint: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return request options passing a grammar/regex decoding constraint."""
        ...
