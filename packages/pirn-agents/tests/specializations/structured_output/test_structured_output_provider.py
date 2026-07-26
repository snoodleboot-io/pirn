"""Contract tests for the :class:`StructuredOutputProvider` base class (WS1·S4).

Locks in the house interface style: a `NotImplementedError` base that subclasses
core `LLMProvider` (a strict superset), so the unified decoder's
`isinstance(llm, StructuredOutputProvider)` probes are real nominal subtype
checks. After WS4·S1's ISP split the *thin* `BaseLLMProvider` deliberately does
**not** carry the seam (plain-chat clients don't depend on it); the HTTP
structured seam `HttpStructuredOutputProvider` and the vendor providers subclass
it explicitly.
"""

from __future__ import annotations

import unittest

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.anthropic_messages_provider import AnthropicMessagesProvider
from pirn_agents.llm.base_llm_provider import BaseLLMProvider
from pirn_agents.llm.http_structured_output_provider import HttpStructuredOutputProvider
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)


class TestStructuredOutputProviderContract(unittest.IsolatedAsyncioTestCase):
    def test_base_subclasses_llm_provider_and_is_opaque(self) -> None:
        # Arrange / Act / Assert: superset of LLMProvider, inherits the opaque contract.
        self.assertTrue(issubclass(StructuredOutputProvider, LLMProvider))
        self.assertTrue(issubclass(StructuredOutputProvider, PirnOpaqueValue))

    def test_thin_base_does_not_carry_the_seam(self) -> None:
        # Arrange / Act / Assert (ISP): the thin base is a plain LLMProvider only —
        # it must NOT nominally carry the structured-output seam.
        self.assertTrue(issubclass(BaseLLMProvider, LLMProvider))
        self.assertFalse(issubclass(BaseLLMProvider, StructuredOutputProvider))

    def test_http_seam_and_vendor_providers_subclass_base(self) -> None:
        # Arrange / Act / Assert: the HTTP seam and every vendor provider declare
        # the structured-output base nominally, so isinstance probes route them native.
        self.assertTrue(issubclass(HttpStructuredOutputProvider, StructuredOutputProvider))
        self.assertTrue(issubclass(HttpStructuredOutputProvider, BaseLLMProvider))
        self.assertTrue(issubclass(OpenAICompatibleProvider, StructuredOutputProvider))
        self.assertTrue(issubclass(AnthropicMessagesProvider, StructuredOutputProvider))

    def test_capability_defaults_to_all_false(self) -> None:
        # Arrange: a bare base instance (interface style — instantiable, no abc).
        provider = StructuredOutputProvider()

        # Act: the default advertises no native mechanism.
        capability = provider.structured_output_capability()

        # Assert: matches an all-false capability so the decoder falls back.
        self.assertEqual(capability, StructuredOutputCapability())
        self.assertFalse(capability.native_schema)
        self.assertFalse(capability.forced_tool_choice)
        self.assertFalse(capability.constrained_decoding)

    async def test_native_methods_raise_not_implemented(self) -> None:
        # Arrange: a bare base instance.
        provider = StructuredOutputProvider()

        # Act / Assert: each native-mechanism method reports the owning class.
        with self.assertRaisesRegex(NotImplementedError, "StructuredOutputProvider"):
            await provider.structured_chat([{"role": "user", "content": "hi"}])
        with self.assertRaisesRegex(NotImplementedError, "StructuredOutputProvider"):
            provider.native_schema_option({}, name="x")
        with self.assertRaisesRegex(NotImplementedError, "StructuredOutputProvider"):
            provider.forced_tool_choice_option("extract")
        with self.assertRaisesRegex(NotImplementedError, "StructuredOutputProvider"):
            provider.constrained_decoding_option({})


if __name__ == "__main__":
    unittest.main()
