"""``ConstrainedDecodingStrategy`` — the grammar/regex-constrained decode path.

Gated on the ``constrained_decoding`` capability flag. Maps the target model
onto the provider's native decode options via
:class:`pirn_agents.specializations.structured_output.constrained_decoding_mapper.ConstrainedDecodingMapper`,
issues one ``structured_chat`` call, and validates the returned content through a
:class:`pirn_agents.specializations.structured_output.structured_content_validator.StructuredContentValidator`.
"""

from __future__ import annotations

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.constrained_decoding_mapper import (
    ConstrainedDecodingMapper,
)
from pirn_agents.specializations.structured_output.native_decode_strategy import (
    NativeDecodeStrategy,
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


class ConstrainedDecodingStrategy(NativeDecodeStrategy):
    """Decode via the provider's grammar/regex-constrained decode options."""

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
        """Return whether the provider advertises constrained decoding."""
        return capability.constrained_decoding

    async def try_decode(self, *, prompt: str, provider: StructuredOutputProvider) -> BaseModel:
        """Decode ``prompt`` via the provider's constrained-decoding options."""
        options = ConstrainedDecodingMapper(schema=self._model_class).map_request(provider)
        if options is None:
            raise StructuredDecodeError(
                "ConstrainedDecodingStrategy: constrained decoding unsupported"
            )
        response = await provider.structured_chat(
            [{"role": "user", "content": prompt}], request_options=options
        )
        return self._validator.validate(response.content)
