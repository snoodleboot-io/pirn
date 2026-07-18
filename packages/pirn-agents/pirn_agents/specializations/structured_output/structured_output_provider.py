"""``StructuredOutputProvider`` — the provider seam the native strategies use.

A base class describing the small surface a provider must expose for the F20
native structured-output paths. It is a **strict superset of the plain**
:class:`pirn.core.providers.llm_provider.LLMProvider` contract, so it subclasses
``LLMProvider`` directly: capability advertisement plus a single structured chat
call and three request-option shapers, one per native mechanism. Inheriting
``LLMProvider`` also carries the :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`
opaque contract, so a live provider crosses the Knot IO boundary by ``isinstance``.

Following the house interface style (never :class:`typing.Protocol`), the base
raises :class:`NotImplementedError` for the four native-mechanism methods and
defaults :meth:`structured_output_capability` to advertise **nothing**. That safe
default lets the unified decoder (S4) probe a provider with :func:`isinstance`
and degrade gracefully — a provider subclassing this base but not overriding the
capability routes straight to the extract-validate-retry fallback, and a plain
``LLMProvider`` (not a subclass) never enters the native path at all. Every
vendor-specific wire shape stays behind the provider's own override of the option
shapers, so no strategy embeds a provider-specific code path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.toolset import Toolset
from pirn_agents.types.agent_response import AgentResponse


class StructuredOutputProvider(LLMProvider):
    """Provider base for native structured-output decoding (superset of LLMProvider)."""

    def structured_output_capability(self) -> StructuredOutputCapability:
        """Return the provider's advertised native structured-output flags.

        Defaults to advertising no native support, so a provider that subclasses
        this base without overriding routes the unified decoder straight to the
        extract-validate-retry fallback.
        """
        return StructuredOutputCapability()

    async def structured_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tools: Toolset | None = None,
        request_options: Mapping[str, Any] | None = None,
    ) -> AgentResponse:
        """Send a chat completion merging ``request_options`` into the request."""
        raise NotImplementedError(f"{type(self).__name__} must implement structured_chat()")

    def native_schema_option(self, schema: Mapping[str, Any], *, name: str) -> Mapping[str, Any]:
        """Return request options carrying a native schema/``response_format``."""
        raise NotImplementedError(f"{type(self).__name__} must implement native_schema_option()")

    def forced_tool_choice_option(self, tool_name: str) -> Mapping[str, Any]:
        """Return request options forcing a single named tool call."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement forced_tool_choice_option()"
        )

    def constrained_decoding_option(self, constraint: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return request options passing a grammar/regex decoding constraint."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement constrained_decoding_option()"
        )
