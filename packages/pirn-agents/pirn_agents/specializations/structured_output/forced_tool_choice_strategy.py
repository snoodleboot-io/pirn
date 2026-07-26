"""``ForcedToolChoiceStrategy`` — the forced tool-choice decode path.

Gated on the ``forced_tool_choice`` capability flag. Delegates the single-pass
extraction to
:class:`pirn_agents.specializations.structured_output.forced_tool_choice_extractor.ForcedToolChoiceExtractor`,
which forces one synthetic tool call and validates its decoded arguments.
"""

from __future__ import annotations

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.forced_tool_choice_extractor import (
    ForcedToolChoiceExtractor,
)
from pirn_agents.specializations.structured_output.native_decode_strategy import (
    NativeDecodeStrategy,
)
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)


class ForcedToolChoiceStrategy(NativeDecodeStrategy):
    """Decode by forcing a single synthetic tool call and validating its args."""

    def __init__(
        self,
        *,
        model_class: type[BaseModel],
        tool_name: str,
    ) -> None:
        """Bind the strategy to a target model and the synthetic tool name.

        Args:
            model_class: The :class:`pydantic.BaseModel` subclass to extract.
            tool_name: The name of the synthetic extraction tool to force.
        """
        self._model_class = model_class
        self._tool_name = tool_name

    def is_advertised(self, capability: StructuredOutputCapability) -> bool:
        """Return whether the provider advertises forced tool-choice."""
        return capability.forced_tool_choice

    async def try_decode(self, *, prompt: str, provider: StructuredOutputProvider) -> BaseModel:
        """Decode ``prompt`` by forcing a single named tool call."""
        return await ForcedToolChoiceExtractor(
            model_class=self._model_class, tool_name=self._tool_name
        ).extract(prompt=prompt, provider=provider)
