"""HTTP LLM providers hash by a credential-free content identity (PIR-840 PR-3).

``BaseLLMProvider`` inherits an identity-keyed ``__pirn_canonical__`` from
``ConnectorBase`` (PIR-848), so a recorded run could never replay in another
process. A provider class that re-declares ``content_identity`` now hashes by its
class, model, endpoint and request settings instead, and falls back to identity
whenever that configuration cannot be captured safely. The per-argument coverage
lives in ``test_llm_provider_identity_gate.py``; secret absence in
``test_llm_provider_identity_secrets.py``.
"""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from typing import Any, ClassVar

from pirn.core.hashing import content_hash
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.run_request import RunRequest
from pirn.recording.replay_mismatch_error import ReplayMismatchError
from pirn.recording.replay_session import ReplaySession
from pirn.security.credential_ref import CredentialRef
from pirn.tapestry import Tapestry

from pirn_agents.llm.anthropic_messages_provider import AnthropicMessagesProvider
from pirn_agents.llm.base_llm_provider import BaseLLMProvider
from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from pirn_agents.llm.retry_policy import RetryPolicy
from tests.llm.test_base_llm_provider import StubLLMProvider

PROVIDERS: tuple[type[BaseLLMProvider], ...] = (OpenAICompatibleProvider, AnthropicMessagesProvider)


class _UndeclaredOpenAICompatibleProvider(OpenAICompatibleProvider):
    """Inherits the opt-in without re-declaring it, so it must stay identity-keyed."""

    def _completions_path(self) -> str:
        return "/tenant-a/chat/completions"


class _RedeclaredOpenAICompatibleProvider(OpenAICompatibleProvider):
    """Re-declares the opt-in, asserting it adds no behaviour-relevant config."""

    def content_identity(self) -> Any:
        return super().content_identity()


@dataclass(frozen=True)
class _DiscountedPricing(ModelPricing):
    """A pricing subclass whose cost is not what its fields say."""

    def estimate_cost(self, usage: Any) -> float:
        return 0.0


@dataclass(frozen=True)
class _PatientRetryPolicy(RetryPolicy):
    """A retry-policy subclass whose backoff is not what its fields say."""

    def backoff_delay(self, attempt: int, *, rng: Any = None) -> float:
        return 0.0


class AsksModel(Knot):
    """Holds a provider as a literal and reports the model it is configured for."""

    invocations: ClassVar[list[str]] = []

    def __init__(self, *, llm: BaseLLMProvider, **kwargs: Any) -> None:
        super().__init__(llm=llm, **kwargs)

    async def process(self, llm: BaseLLMProvider, **_: Any) -> str:
        AsksModel.invocations.append(llm._model)
        return f"answered-by-{llm._model}"


def make_local_provider_class() -> type[OpenAICompatibleProvider]:
    """Return a provider class defined per call, so every such class shares a qualname."""

    # design-decision-override: a factory-local class is the case under test.
    class Local(OpenAICompatibleProvider):
        def content_identity(self) -> Any:
            return super().content_identity()

    return Local


class TestContentIdentifiedProvidersHashByConfiguration(unittest.TestCase):
    def test_identically_configured_separate_providers_hash_equal(self) -> None:
        for provider_type in PROVIDERS:
            with self.subTest(provider=provider_type.__name__):
                # Arrange
                first = provider_type(model="m-a", base_url="https://a.example/v1")
                second = provider_type(model="m-a", base_url="https://a.example/v1")

                # Act / Assert
                assert content_hash(first) == content_hash(second)

    def test_the_provider_class_separates_equal_configurations(self) -> None:
        # Arrange
        chat = OpenAICompatibleProvider(model="m", base_url="https://a.example/v1")
        messages = AnthropicMessagesProvider(model="m", base_url="https://a.example/v1")

        # Act / Assert
        assert content_hash(chat) != content_hash(messages)

    def test_the_canonical_form_names_the_class_and_its_configuration(self) -> None:
        # Arrange
        provider = AnthropicMessagesProvider(
            model="m-a",
            base_url="https://A.Example:8443/v1/",
            pricing=ModelPricing(input_per_million=1.0),
            default_max_tokens=64,
            enable_prompt_cache=True,
            timeout=12.5,
        )

        # Act
        canonical = provider.__pirn_canonical__()

        # Assert
        assert canonical == {
            "__pirn_type__": "llm_provider",
            "provider": "pirn_agents.llm.anthropic_messages_provider.AnthropicMessagesProvider",
            "config": {
                "model": "m-a",
                "endpoint": {"scheme": "https", "host": "a.example", "port": 8443, "path": "/v1"},
                "default_max_tokens": 64,
                "enable_prompt_cache": True,
                "pricing": {
                    "input_per_million": 1.0,
                    "output_per_million": 0.0,
                    "cached_input_per_million": 0.0,
                },
                "timeout": 12.5,
                "retry_policy": {
                    "max_retries": 2,
                    "base_delay": 0.05,
                    "max_delay": 2.0,
                    "multiplier": 2.0,
                    "max_retry_after": 60.0,
                    "jitter": True,
                },
            },
        }

    def test_each_endpoint_component_changes_the_hash(self) -> None:
        # Arrange
        reference = content_hash(
            OpenAICompatibleProvider(model="m", base_url="https://a.example/v1")
        )
        variants = (
            "http://a.example/v1",
            "https://b.example/v1",
            "https://a.example:8443/v1",
            "https://a.example/v2",
            "https://a.example",
        )

        for base_url in variants:
            with self.subTest(base_url=base_url):
                # Act
                varied = OpenAICompatibleProvider(model="m", base_url=base_url)

                # Assert
                assert varied.content_identity() is not None
                assert content_hash(varied) != reference

    def test_host_case_and_trailing_slashes_do_not_change_the_hash(self) -> None:
        # Arrange — the provider joins base_url.rstrip("/") with its path, and DNS
        # names are case-insensitive, so these address the same endpoint.
        reference = OpenAICompatibleProvider(model="m", base_url="https://a.example/v1")
        same = OpenAICompatibleProvider(model="m", base_url="HTTPS://A.EXAMPLE/v1//")

        # Act / Assert
        assert content_hash(same) == content_hash(reference)

    def test_every_value_of_retry_policy_changes_the_hash(self) -> None:
        # Arrange
        reference = content_hash(OpenAICompatibleProvider(model="m", base_url="https://a/v1"))
        policies = (
            RetryPolicy(max_retries=5),
            RetryPolicy(base_delay=1.0),
            RetryPolicy(max_delay=9.0),
            RetryPolicy(multiplier=3.0),
            RetryPolicy(jitter=False),
            RetryPolicy(max_retry_after=1.0),
        )

        for policy in policies:
            with self.subTest(policy=policy):
                # Act
                varied = OpenAICompatibleProvider(
                    model="m", base_url="https://a/v1", retry_policy=policy
                )

                # Assert
                assert content_hash(varied) != reference

    def test_every_price_changes_the_hash(self) -> None:
        # Arrange
        reference = content_hash(
            OpenAICompatibleProvider(model="m", base_url="https://a/v1", pricing=ModelPricing())
        )
        sheets = (
            None,
            ModelPricing(input_per_million=1.0),
            ModelPricing(output_per_million=1.0),
            ModelPricing(cached_input_per_million=1.0),
        )

        for pricing in sheets:
            with self.subTest(pricing=pricing):
                # Act
                varied = OpenAICompatibleProvider(
                    model="m", base_url="https://a/v1", pricing=pricing
                )

                # Assert
                assert content_hash(varied) != reference

    def test_a_plain_mapping_of_the_same_shape_does_not_hash_like_a_provider(self) -> None:
        # Arrange
        provider = OpenAICompatibleProvider(model="m", base_url="https://a/v1")
        canonical = provider.__pirn_canonical__()
        lookalike = {"provider": canonical["provider"], "config": canonical["config"]}

        # Act / Assert
        assert content_hash(lookalike) != content_hash(provider)

    def test_the_hash_follows_the_pricing_and_retry_policy_that_actually_run(self) -> None:
        """Swapping a private attribute after construction must not re-key the hash.

        The constructor hands pricing to the response mapper and the retry policy to
        the transport; those are what compute ``cost`` and retry. A hash read from the
        provider's own attributes would describe a config that never runs.
        """
        # Arrange
        provider = OpenAICompatibleProvider(
            model="m",
            base_url="https://a/v1",
            pricing=ModelPricing(input_per_million=1.0),
            retry_policy=RetryPolicy(max_retries=2),
        )
        before = content_hash(provider)
        running_cost = provider._mapper.estimate_cost({"input_tokens": 1_000_000})

        # Act
        provider._pricing = ModelPricing(input_per_million=99.0)
        provider._retry_policy = RetryPolicy(max_retries=0)

        # Assert — cost and retries still come from the built collaborators, and so does the hash.
        assert provider._mapper.estimate_cost({"input_tokens": 1_000_000}) == running_cost
        assert provider._transport.retry_policy == RetryPolicy(max_retries=2)
        assert content_hash(provider) == before
        assert provider.__pirn_canonical__()["config"]["pricing"]["input_per_million"] == 1.0
        assert provider.__pirn_canonical__()["config"]["retry_policy"]["max_retries"] == 2

    def test_a_replaced_mapper_falls_back(self) -> None:
        # Arrange
        provider = OpenAICompatibleProvider(model="m", base_url="https://a/v1")
        provider._mapper = type("_Mapper", (type(provider._mapper),), {})(
            codec=provider._codec, pricing=None
        )

        # Act / Assert
        assert provider.content_identity() is None

    def test_the_hash_is_stable_across_close_and_credential_clearing(self) -> None:
        # Arrange
        provider = OpenAICompatibleProvider(
            model="m", base_url="https://a/v1", credential=CredentialRef(secret="sk-X")
        )
        before = content_hash(provider)

        # Act
        asyncio.run(provider.close())

        # Assert
        assert provider._credential is None
        assert content_hash(provider) == before

    def test_the_audit_form_is_unchanged(self) -> None:
        # Arrange
        provider = OpenAICompatibleProvider(
            model="m", base_url="https://a/v1", credential=CredentialRef(secret="sk-X")
        )

        # Act / Assert
        assert provider._pirn_audit_dict() == {
            "connector": "OpenAICompatibleProvider",
            "has_credential": True,
        }


class TestProvidersFallBackToIdentity(unittest.TestCase):
    def assert_identity_keyed(self, first: BaseLLMProvider, second: BaseLLMProvider) -> None:
        assert first.__pirn_canonical__() == PirnOpaqueValue._pirn_audit_dict(first)
        assert content_hash(first) != content_hash(second)
        assert content_hash(first) == content_hash(first)

    def test_a_subclass_that_does_not_redeclare_the_opt_in_is_identity_keyed(self) -> None:
        # Arrange
        first = _UndeclaredOpenAICompatibleProvider(model="m", base_url="https://a/v1")
        second = _UndeclaredOpenAICompatibleProvider(model="m", base_url="https://a/v1")

        # Act / Assert — the subclass changes the request path its config does not show.
        assert first.content_identity() is not None
        self.assert_identity_keyed(first, second)

    def test_a_subclass_that_redeclares_the_opt_in_is_named_by_its_own_class(self) -> None:
        # Arrange
        provider = _RedeclaredOpenAICompatibleProvider(model="m", base_url="https://a/v1")
        parent = OpenAICompatibleProvider(model="m", base_url="https://a/v1")

        # Act
        canonical = provider.__pirn_canonical__()

        # Assert
        assert canonical["provider"].endswith(
            "test_llm_provider_content_identity._RedeclaredOpenAICompatibleProvider"
        )
        assert content_hash(provider) != content_hash(parent)

    def test_a_factory_built_class_is_identity_keyed_even_when_it_redeclares(self) -> None:
        # Arrange
        first = make_local_provider_class()(model="m", base_url="https://a/v1")
        second = make_local_provider_class()(model="m", base_url="https://a/v1")

        # Act / Assert
        self.assert_identity_keyed(first, second)

    def test_a_provider_that_never_declared_the_opt_in_is_identity_keyed(self) -> None:
        # Arrange
        first = StubLLMProvider(model="m", base_url="https://a/v1")
        second = StubLLMProvider(model="m", base_url="https://a/v1")

        # Act / Assert
        self.assert_identity_keyed(first, second)

    def test_injected_collaborators_fall_back(self) -> None:
        async def other_sleep(delay: float) -> None:
            return None

        injected: dict[str, dict[str, Any]] = {
            "client": {"client": object()},
            "sleeper": {"sleeper": other_sleep},
            "rng": {"rng": lambda: 0.5},
        }
        for label, kwargs in injected.items():
            with self.subTest(injected=label):
                # Arrange
                first = OpenAICompatibleProvider(model="m", base_url="https://a/v1", **kwargs)
                second = OpenAICompatibleProvider(model="m", base_url="https://a/v1", **kwargs)

                # Act / Assert
                assert first.content_identity() is None
                self.assert_identity_keyed(first, second)

    def test_the_default_sleeper_passed_explicitly_is_not_an_injection(self) -> None:
        # Arrange
        provider = OpenAICompatibleProvider(
            model="m", base_url="https://a/v1", sleeper=asyncio.sleep
        )

        # Act / Assert
        assert provider.content_identity() is not None

    def test_a_replaced_transport_falls_back(self) -> None:
        # Arrange
        provider = OpenAICompatibleProvider(model="m", base_url="https://a/v1")
        provider._transport = type("_Transport", (type(provider._transport),), {})(
            retry_policy=RetryPolicy(), sleeper=asyncio.sleep, rng=None
        )

        # Act / Assert
        assert provider.content_identity() is None

    def test_subclassed_pricing_or_retry_policy_falls_back(self) -> None:
        values: dict[str, dict[str, Any]] = {
            "pricing": {"pricing": _DiscountedPricing(input_per_million=1.0)},
            "retry_policy": {"retry_policy": _PatientRetryPolicy()},
        }
        for label, kwargs in values.items():
            with self.subTest(value=label):
                # Arrange
                provider = OpenAICompatibleProvider(model="m", base_url="https://a/v1", **kwargs)

                # Act / Assert
                assert provider.content_identity() is None

    def test_non_plain_numeric_settings_fall_back(self) -> None:
        values: dict[str, dict[str, Any]] = {
            "bool max tokens": {"default_max_tokens": True},
            "float max tokens": {"default_max_tokens": 1.5},
            "string price": {"pricing": ModelPricing(input_per_million="1")},  # type: ignore[arg-type]
            "string retries": {"retry_policy": RetryPolicy(max_retries="2")},  # type: ignore[arg-type]
            "int jitter": {"retry_policy": RetryPolicy(jitter=1)},  # type: ignore[arg-type]
        }
        for label, kwargs in values.items():
            with self.subTest(value=label):
                # Arrange
                provider = OpenAICompatibleProvider(model="m", base_url="https://a/v1", **kwargs)

                # Act / Assert
                assert provider.content_identity() is None

    def test_unsafe_base_urls_fall_back(self) -> None:
        unsafe = (
            "https://user:pw@a.example/v1",
            "https://a.example/v1?api-version=1",
            "https://a.example/v1?",
            "https://a.example/v1#frag",
            "ftp://a.example/v1",
            "a.example/v1",
        )
        for base_url in unsafe:
            with self.subTest(base_url=base_url):
                # Arrange
                first = OpenAICompatibleProvider(model="m", base_url=base_url)
                second = OpenAICompatibleProvider(model="m", base_url=base_url)

                # Act / Assert
                assert first.content_identity() is None
                self.assert_identity_keyed(first, second)


class TestInProcessReplayUsesContentIdentity(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        AsksModel.invocations.clear()

    async def test_a_separately_built_provider_with_the_same_config_is_served(self) -> None:
        # Arrange
        recorded_with = OpenAICompatibleProvider(
            model="m-a", base_url="https://a.example/v1", credential=CredentialRef(secret="sk-A")
        )
        with Tapestry() as recorded:
            AsksModel(llm=recorded_with, _config=KnotConfig(id="ask"))
        original = await recorded.run(RunRequest())
        rebuilt = OpenAICompatibleProvider(
            model="m-a", base_url="https://a.example/v1", credential=CredentialRef(secret="sk-B")
        )
        with Tapestry(history=recorded.history, data_store=recorded.data_store) as replaying:
            AsksModel(llm=rebuilt, _config=KnotConfig(id="ask"))
        session = await ReplaySession.from_history(history=recorded.history, run_id=original.run_id)

        # Act
        replayed = await replaying.run(RunRequest(), replay=session)

        # Assert
        assert replayed.outputs["ask"] == "answered-by-m-a"
        assert AsksModel.invocations == ["m-a"]

    async def test_a_provider_with_another_model_refuses(self) -> None:
        # Arrange
        with Tapestry() as recorded:
            AsksModel(
                llm=OpenAICompatibleProvider(model="m-a", base_url="https://a.example/v1"),
                _config=KnotConfig(id="ask"),
            )
        original = await recorded.run(RunRequest())
        with Tapestry(history=recorded.history, data_store=recorded.data_store) as replaying:
            AsksModel(
                llm=OpenAICompatibleProvider(model="m-b", base_url="https://a.example/v1"),
                _config=KnotConfig(id="ask"),
            )
        session = await ReplaySession.from_history(history=recorded.history, run_id=original.run_id)

        # Act / Assert
        with self.assertRaises(ReplayMismatchError):
            await replaying.run(RunRequest(), replay=session)
        assert AsksModel.invocations == ["m-a"]
