"""``ForcedToolChoiceExtractor`` — one-pass extraction via a forced tool call.

The S2 building block. It synthesises a single :class:`_ExtractionTool` whose
parameters are the target model's JSON schema, declares it to the provider
through F1's :class:`pirn_agents.tool_call_codec.ToolCallCodec` (the codec the
provider already drives), and forces tool-choice to that one tool. The provider
returns a single tool call whose arguments — decoded by the codec — are
validated against the model in one pass, with no retry round-trip.

The "force this tool" wire shape is provided by the provider's
``forced_tool_choice_option`` boundary, so this extractor stays
provider-neutral.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from pirn_agents.specializations.structured_output._extraction_tool import _ExtractionTool
from pirn_agents.specializations.structured_output.structured_decode_error import (
    StructuredDecodeError,
)
from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)
from pirn_agents.toolset import Toolset


class ForcedToolChoiceExtractor:
    """Extract a validated model instance by forcing a single tool call."""

    def __init__(
        self,
        *,
        model_class: type[BaseModel],
        tool_name: str = "extract",
        description: str = "Return the requested structured data.",
    ) -> None:
        """Bind the extractor to a target model and the synthetic tool identity.

        Args:
            model_class: The :class:`pydantic.BaseModel` subclass to extract.
            tool_name: The name of the synthetic extraction tool to force.
            description: The synthetic tool's description declared to the LLM.

        Raises:
            TypeError: If ``model_class`` is not a ``BaseModel`` subclass or
                ``tool_name`` is not a non-empty string.
        """
        if not isinstance(model_class, type) or not issubclass(model_class, BaseModel):
            raise TypeError(
                "ForcedToolChoiceExtractor: model_class must be a BaseModel "
                f"subclass, got {model_class!r}"
            )
        if not isinstance(tool_name, str) or not tool_name:
            raise TypeError(
                f"ForcedToolChoiceExtractor: tool_name must be a non-empty str, got {tool_name!r}"
            )
        self._model_class = model_class
        self._tool_name = tool_name
        self._description = description

    def toolset(self) -> Toolset:
        """Return the single-tool toolset the forced call is declared from."""
        tool = _ExtractionTool(
            name=self._tool_name,
            description=self._description,
            parameters_schema=self._model_class.model_json_schema(),
        )
        return Toolset([tool])

    async def extract(self, *, prompt: str, provider: StructuredOutputProvider) -> BaseModel:
        """Force a single tool call and validate its arguments against the model.

        Args:
            prompt: The extraction prompt sent as a single user message.
            provider: A capability-advertising :class:`StructuredOutputProvider`.

        Returns:
            A validated model instance built from the forced tool call's
            decoded arguments.

        Raises:
            TypeError: If ``prompt`` is not a string or ``provider`` is not a
                :class:`StructuredOutputProvider`.
            StructuredDecodeError: If the provider does not advertise forced
                tool-choice, returns no tool call, or the decoded arguments fail
                model validation.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                f"ForcedToolChoiceExtractor: prompt must be a str, got {type(prompt).__name__}"
            )
        if not isinstance(provider, StructuredOutputProvider):
            raise TypeError(
                "ForcedToolChoiceExtractor: provider must be a "
                f"StructuredOutputProvider, got {type(provider).__name__}"
            )
        if not provider.structured_output_capability().forced_tool_choice:
            raise StructuredDecodeError(
                "ForcedToolChoiceExtractor: provider does not advertise forced tool-choice"
            )
        options = provider.forced_tool_choice_option(self._tool_name)
        response = await provider.structured_chat(
            [{"role": "user", "content": prompt}],
            tools=self.toolset(),
            request_options=options,
        )
        call = self._single_call(response.tool_calls)
        try:
            return self._model_class.model_validate(dict(call.arguments))
        except ValidationError as exc:
            raise StructuredDecodeError(
                f"ForcedToolChoiceExtractor: forced tool arguments failed validation: {exc}"
            ) from exc

    def _single_call(self, tool_calls: Any) -> Any:
        for call in tool_calls:
            if call.tool_name == self._tool_name:
                return call
        if tool_calls:
            return tool_calls[0]
        raise StructuredDecodeError(
            "ForcedToolChoiceExtractor: provider returned no tool call to extract from"
        )
