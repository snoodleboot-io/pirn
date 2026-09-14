"""HTTP LLM providers never replay another model's or endpoint's recording (PIR-848).

``BaseLLMProvider`` inherits ``ConnectorBase``, whose audit form is the constant
``{connector, has_credential}``.  Before PIR-848 that constant was the provider's
content hash, so ``OpenAICompatibleProvider(model="m-a", base_url=a)`` and
``(model="m-b", base_url=b)`` hashed equal and core replay served a recording
made with one to a run configured with the other.  The ``ConnectorBase`` default
is now identity-keyed.  PIR-840 PR-3 opts the concrete HTTP providers back into a
credential-free content form (``test_llm_provider_content_identity.py``); a provider
that cannot be named safely keeps the identity token.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

import pytest
from pirn.core.content_hasher import ContentHasher
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.recording.replay_mismatch_error import ReplayMismatchError
from pirn.recording.replay_session import ReplaySession
from pirn.security.credential_ref import CredentialRef
from pirn.tapestry import Tapestry

from pirn_agents.llm.anthropic_messages_provider import AnthropicMessagesProvider
from pirn_agents.llm.base_llm_provider import BaseLLMProvider
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider


class AsksModel(Knot):
    """Holds a provider as a literal and reports the model it is configured for."""

    invocations: ClassVar[list[str]] = []

    def __init__(self, *, llm: BaseLLMProvider, **kwargs: Any) -> None:
        super().__init__(llm=llm, **kwargs)

    async def process(self, llm: BaseLLMProvider, **_: Any) -> str:
        AsksModel.invocations.append(llm._model)
        return f"answered-by-{llm._model}"


@pytest.fixture(autouse=True)
def _clear_invocations() -> None:
    AsksModel.invocations.clear()


@pytest.mark.parametrize("provider_cls", [OpenAICompatibleProvider, AnthropicMessagesProvider])
def test_live_providers_with_different_model_and_endpoint_hash_differently(
    provider_cls: type[BaseLLMProvider],
) -> None:
    # Arrange
    provider_a = provider_cls(model="m-a", base_url="https://a.example/v1")
    provider_b = provider_cls(model="m-b", base_url="https://b.example/v1")

    # Act
    hash_a = ContentHasher.hash({"llm": provider_a})
    hash_b = ContentHasher.hash({"llm": provider_b})

    # Assert
    assert hash_a != hash_b


def test_identically_configured_separate_providers_hash_equal() -> None:
    # Arrange — PIR-840 PR-3 gives the concrete providers content identity.
    first = OpenAICompatibleProvider(model="m-a", base_url="https://a.example/v1")
    second = OpenAICompatibleProvider(model="m-a", base_url="https://a.example/v1")

    # Act
    hashes = {ContentHasher.hash({"llm": first}), ContentHasher.hash({"llm": second})}

    # Assert
    assert len(hashes) == 1


def test_identically_configured_providers_that_cannot_be_named_hash_differently() -> None:
    # Arrange — an injected client keeps the PIR-848 identity semantics.
    first = OpenAICompatibleProvider(model="m-a", base_url="https://a.example/v1", client=object())
    second = OpenAICompatibleProvider(model="m-a", base_url="https://a.example/v1", client=object())

    # Act
    hashes = {ContentHasher.hash({"llm": first}), ContentHasher.hash({"llm": second})}

    # Assert
    assert len(hashes) == 2


def test_provider_hash_is_stable_across_calls() -> None:
    # Arrange
    provider = OpenAICompatibleProvider(model="m-a", base_url="https://a.example/v1")

    # Act
    hashes = {ContentHasher.hash(provider) for _ in range(5)}

    # Assert
    assert len(hashes) == 1


def test_provider_audit_dict_output_is_unchanged() -> None:
    # Arrange
    provider = OpenAICompatibleProvider(
        model="m-a",
        base_url="https://a.example/v1",
        credential=CredentialRef(secret="sk-PIR848-SENTINEL"),
    )

    # Act
    audit = provider._pirn_audit_dict()

    # Assert
    assert audit == {"connector": "OpenAICompatibleProvider", "has_credential": True}


def test_no_credential_or_configuration_appears_in_an_identity_keyed_canonical_form() -> None:
    # Arrange — an injected client keeps the provider identity-keyed.
    secret = "sk-PIR848-SENTINEL"
    provider = OpenAICompatibleProvider(
        model="m-a",
        base_url="https://a.example/v1",
        credential=CredentialRef(secret=secret),
        client=object(),
    )

    # Act — the canonical form and the token are what ContentHasher.hash consumes.
    canonical = json.dumps(provider.__pirn_canonical__())
    token = provider._pirn_identity_token()

    # Assert
    for form in (canonical, token):
        assert secret not in form
        assert "a.example" not in form
        assert "m-a" not in form


async def test_replay_refuses_a_recording_made_with_another_model_and_endpoint() -> None:
    # Arrange — record with provider config A.
    provider_a = OpenAICompatibleProvider(
        model="m-a", base_url="https://a.example/v1", credential=CredentialRef(secret="sk-AAAA")
    )
    with Tapestry() as recorded:
        AsksModel(llm=provider_a, _config=KnotConfig(id="ask"))
    original = await recorded.run(RunRequest())

    provider_b = OpenAICompatibleProvider(
        model="m-b", base_url="https://b.example/v1", credential=CredentialRef(secret="sk-BBBB")
    )
    with Tapestry(history=recorded.history, data_store=recorded.data_store) as reconfigured:
        AsksModel(llm=provider_b, _config=KnotConfig(id="ask"))
    session = await ReplaySession.from_history(history=recorded.history, run_id=original.run_id)

    # Act / Assert — refused, not served "answered-by-m-a".
    with pytest.raises(ReplayMismatchError) as caught:
        await reconfigured.run(RunRequest(), replay=session)
    assert caught.value.knot_id == "ask"
    assert AsksModel.invocations == ["m-a"]


async def test_replay_serves_when_the_recorded_provider_is_reused() -> None:
    # Arrange
    provider = OpenAICompatibleProvider(model="m-a", base_url="https://a.example/v1")
    with Tapestry() as tapestry:
        AsksModel(llm=provider, _config=KnotConfig(id="ask"))
    original = await tapestry.run(RunRequest())
    session = await ReplaySession.from_history(history=tapestry.history, run_id=original.run_id)

    # Act
    replayed = await tapestry.run(RunRequest(), replay=session)

    # Assert
    assert replayed.outputs["ask"] == "answered-by-m-a"
    assert AsksModel.invocations == ["m-a"]
