"""No credential ever reaches an HTTP provider's canonical form (PIR-840 PR-3).

The canonical form is what ``ContentHasher.hash`` digests, and the digest lands in lineage.
These tests assert on the **form** (serialised to JSON), never on the hex digest: a
digest cannot show that a secret is absent, only that two inputs differ.

Sentinels are placed everywhere a secret can hide in a provider's configuration: the
``CredentialRef``, URL userinfo, query parameters commonly used for tokens and signed
requests, and a fragment. Every request header a provider sends is also checked, by
name and value.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any

from pirn.security.credential_ref import CredentialRef

from pirn_agents.llm.anthropic_messages_provider import AnthropicMessagesProvider
from pirn_agents.llm.base_llm_provider import BaseLLMProvider
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider

PROVIDERS: tuple[type[BaseLLMProvider], ...] = (OpenAICompatibleProvider, AnthropicMessagesProvider)
SENTINEL = "SENTINEL-7f3a9c"


def canonical_form(provider: BaseLLMProvider) -> str:
    """Serialise the provider's canonical form exactly as it would be hashed."""
    return json.dumps(provider.__pirn_canonical__(), sort_keys=True)


class TestCredentialsNeverAppearInTheCanonicalForm(unittest.TestCase):
    def test_the_credential_is_absent_from_a_content_identified_form(self) -> None:
        for provider_type in PROVIDERS:
            with self.subTest(provider=provider_type.__name__):
                # Arrange
                provider = provider_type(
                    model="m",
                    base_url="https://api.example/v1",
                    credential=CredentialRef(secret=f"sk-{SENTINEL}"),
                )

                # Act
                form = canonical_form(provider)

                # Assert
                assert isinstance(provider.__pirn_canonical__(), dict)
                assert SENTINEL not in form
                assert "credential" not in form

    def test_no_request_header_name_or_value_appears_in_the_form(self) -> None:
        for provider_type in PROVIDERS:
            with self.subTest(provider=provider_type.__name__):
                # Arrange
                provider = provider_type(
                    model="m",
                    base_url="https://api.example/v1",
                    credential=CredentialRef(secret=f"sk-{SENTINEL}"),
                )
                headers = provider._request_headers()

                # Act
                form = canonical_form(provider)

                # Assert
                assert any(SENTINEL in value for value in headers.values())
                for name, value in headers.items():
                    assert name not in form
                    assert value not in form

    def test_secrets_in_the_base_url_never_appear_and_force_identity(self) -> None:
        urls = {
            "userinfo": f"https://user:{SENTINEL}@api.example/v1",
            "token as username": f"https://{SENTINEL}@api.example/v1",
            "access_token query": f"https://api.example/v1?access_token={SENTINEL}",
            "key query": f"https://api.example/v1?key={SENTINEL}",
            "signed request query": f"https://api.example/v1?X-Amz-Credential={SENTINEL}",
            "auth query": f"https://api.example/v1?auth={SENTINEL}",
            "fragment": f"https://api.example/v1#{SENTINEL}",
        }
        for provider_type in PROVIDERS:
            for label, base_url in urls.items():
                with self.subTest(provider=provider_type.__name__, url=label):
                    # Arrange
                    provider = provider_type(
                        model="m",
                        base_url=base_url,
                        credential=CredentialRef(secret=f"sk-{SENTINEL}"),
                    )

                    # Act
                    canonical: Any = provider.__pirn_canonical__()
                    form = canonical_form(provider)

                    # Assert
                    assert isinstance(canonical, str)
                    assert SENTINEL not in form
                    assert "api.example" not in form

    def test_the_configuration_holds_exactly_the_reviewed_fields(self) -> None:
        """A new field must be reviewed for secrets before it can enter the form."""
        for provider_type in PROVIDERS:
            with self.subTest(provider=provider_type.__name__):
                # Arrange
                provider = provider_type(model="m", base_url="https://api.example/v1")

                # Act
                canonical = provider.__pirn_canonical__()

                # Assert
                assert set(canonical) == {"__pirn_type__", "provider", "config"}
                assert set(canonical["config"]) == {
                    "model",
                    "endpoint",
                    "default_max_tokens",
                    "enable_prompt_cache",
                    "pricing",
                    "timeout",
                    "retry_policy",
                }
                assert set(canonical["config"]["endpoint"]) == {"scheme", "host", "port", "path"}

    def test_the_form_is_unchanged_when_the_credential_is_cleared(self) -> None:
        for provider_type in PROVIDERS:
            with self.subTest(provider=provider_type.__name__):
                # Arrange
                provider = provider_type(
                    model="m",
                    base_url="https://api.example/v1",
                    credential=CredentialRef(secret=f"sk-{SENTINEL}"),
                )
                before = canonical_form(provider)

                # Act
                asyncio.run(provider.close())

                # Assert
                assert canonical_form(provider) == before

    def test_providers_differing_only_in_credential_share_one_form(self) -> None:
        for provider_type in PROVIDERS:
            with self.subTest(provider=provider_type.__name__):
                # Arrange
                with_key = provider_type(
                    model="m",
                    base_url="https://api.example/v1",
                    credential=CredentialRef(secret=f"sk-A-{SENTINEL}"),
                )
                other_key = provider_type(
                    model="m",
                    base_url="https://api.example/v1",
                    credential=CredentialRef(secret=f"sk-B-{SENTINEL}"),
                )
                without_key = provider_type(model="m", base_url="https://api.example/v1")

                # Act
                forms = {canonical_form(p) for p in (with_key, other_key, without_key)}

                # Assert
                assert len(forms) == 1
