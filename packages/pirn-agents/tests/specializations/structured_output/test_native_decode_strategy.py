"""Unit tests for the :class:`NativeDecodeStrategy` interface base."""

from __future__ import annotations

import unittest

from pirn_agents.specializations.structured_output.native_decode_strategy import (
    NativeDecodeStrategy,
)
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from tests.specializations.structured_output.structured_stubs import (
    StubStructuredProvider,
)


class TestNativeDecodeStrategyInterface(unittest.IsolatedAsyncioTestCase):
    def test_is_advertised_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "is_advertised"):
            NativeDecodeStrategy().is_advertised(StructuredOutputCapability())

    async def test_try_decode_raises_not_implemented(self) -> None:
        provider = StubStructuredProvider(capability=StructuredOutputCapability())
        with self.assertRaisesRegex(NotImplementedError, "try_decode"):
            await NativeDecodeStrategy().try_decode(prompt="x", provider=provider)


if __name__ == "__main__":
    unittest.main()
