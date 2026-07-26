"""Unit tests for :class:`ConstrainedDecodingStrategy`."""

from __future__ import annotations

import unittest

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.constrained_decoding_strategy import (
    ConstrainedDecodingStrategy,
)
from pirn_agents.specializations.structured_output.structured_content_validator import (
    StructuredContentValidator,
)
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from tests.specializations.structured_output.structured_stubs import (
    StubStructuredProvider,
    content_response,
)


class _UserRecord(BaseModel):
    name: str
    age: int


def _strategy() -> ConstrainedDecodingStrategy:
    return ConstrainedDecodingStrategy(
        model_class=_UserRecord,
        validator=StructuredContentValidator(model_class=_UserRecord),
    )


class TestConstrainedDecodingStrategy(unittest.IsolatedAsyncioTestCase):
    def test_is_advertised_reads_constrained_decoding_flag(self) -> None:
        strategy = _strategy()

        assert strategy.is_advertised(StructuredOutputCapability(constrained_decoding=True))
        assert not strategy.is_advertised(StructuredOutputCapability(native_schema=True))

    async def test_try_decode_returns_validated_instance(self) -> None:
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(constrained_decoding=True),
            structured_response=content_response('{"name": "Ada", "age": 36}'),
        )

        instance = await _strategy().try_decode(prompt="extract", provider=provider)

        assert isinstance(instance, _UserRecord)
        assert instance.age == 36
        assert "extra_body" in provider.structured_calls[0]["request_options"]


if __name__ == "__main__":
    unittest.main()
