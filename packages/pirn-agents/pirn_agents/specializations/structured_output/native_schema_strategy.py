"""``NativeSchemaStrategy`` — the native schema/``response_format`` decode path.

Gated on the ``native_schema`` capability flag. Maps the target model onto the
provider's native structured-output request via
:class:`pirn_agents.specializations.structured_output.native_schema_mapper.NativeSchemaMapper`,
issues one ``structured_chat`` call, and validates the returned content through a
:class:`pirn_agents.specializations.structured_output.structured_content_validator.StructuredContentValidator`.
"""

from __future__ import annotations

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.native_decode_strategy import (
    NativeDecodeStrategy,
)
from pirn_agents.specializations.structured_output.native_schema_mapper import (
    NativeSchemaMapper,
)
from pirn_agents.specializations.structured_output.structured_content_validator import (
    StructuredContentValidator,
)
from pirn_agents.specializations.structured_output.structured_decode_error import (
    StructuredDecodeError,
)
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)


class NativeSchemaStrategy(NativeDecodeStrategy):
    """Decode via the provider's native schema/``response_format`` request."""

    def __init__(
        self,
        *,
        model_class: type[BaseModel],
        validator: StructuredContentValidator,
    ) -> None:
        """Bind the strategy to a target model and a content validator.

        Args:
            model_class: The :class:`pydantic.BaseModel` subclass to decode.
            validator: The validator used to parse and validate returned content.
        """
        self._model_class = model_class
        self._validator = validator

    def is_advertised(self, capability: StructuredOutputCapability) -> bool:
        """Return whether the provider advertises native schema decoding."""
        return capability.native_schema

    async def try_decode(self, *, prompt: str, provider: StructuredOutputProvider) -> BaseModel:
        """Decode ``prompt`` via the provider's native schema request."""
        options = NativeSchemaMapper(schema=self._model_class).map_request(provider)
        if options is None:
            raise StructuredDecodeError("NativeSchemaStrategy: native schema mapping unsupported")
        response = await provider.structured_chat(
            [{"role": "user", "content": prompt}], request_options=options
        )
        return self._validator.validate(response.content)
