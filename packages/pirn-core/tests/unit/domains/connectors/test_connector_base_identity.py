"""Content-hash identity of :class:`ConnectorBase` (PIR-848).

A connector's audit form is a secret-free per-class constant
(``{connector, has_credential}``).  Before PIR-848 that constant was also its
content hash, so two connectors of one class aimed at different endpoints
hashed equal and replay served one's recording to the other.  These tests pin
the fix: the hash is identity-keyed, the audit form is untouched, and no
credential reaches either form.
"""

from __future__ import annotations

import json

import pytest

from pirn.connectors.connector_base import ConnectorBase
from pirn.connectors.http_connector import HttpConnector
from pirn.core.hashing import content_hash
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.security.credential_ref import CredentialRef


@pytest.fixture
def sentinel_secret() -> str:
    """A recognisable secret the credential-safety tests search for."""
    return "sk-PIR848-SENTINEL-SECRET"


def test_same_class_connectors_with_different_config_do_not_hash_equal() -> None:
    # Arrange
    endpoint_a = HttpConnector(base_url="https://a.example/v1")
    endpoint_b = HttpConnector(base_url="https://b.example/v1")

    # Act
    hash_a = content_hash(endpoint_a)
    hash_b = content_hash(endpoint_b)

    # Assert
    assert hash_a != hash_b


def test_same_class_connectors_with_identical_config_do_not_hash_equal() -> None:
    # Arrange — identity, not content: equal config is still two objects.
    first = HttpConnector(base_url="https://a.example/v1")
    second = HttpConnector(base_url="https://a.example/v1")

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 2


def test_same_instance_hashes_stably_across_calls() -> None:
    # Arrange
    connector = HttpConnector(base_url="https://a.example/v1")

    # Act
    hashes = {content_hash(connector) for _ in range(5)}

    # Assert
    assert len(hashes) == 1


def test_hash_is_stable_across_credential_scrub(sentinel_secret: str) -> None:
    # Arrange — has_credential flips on scrub; the hash must not follow it.
    connector = ConnectorBase(credential=CredentialRef(secret=sentinel_secret))
    before = content_hash(connector)

    # Act
    connector._clear_credentials()

    # Assert
    assert content_hash(connector) == before


def test_canonical_form_is_the_opaque_value_identity_token() -> None:
    # Arrange
    connector = HttpConnector(base_url="https://a.example/v1")

    # Act
    canonical = connector.__pirn_canonical__()

    # Assert
    assert canonical == PirnOpaqueValue._pirn_audit_dict(connector)
    assert canonical == f"<HttpConnector@{id(connector):x}>"


def test_hash_is_a_comparable_digest_not_the_unhashable_marker() -> None:
    # Arrange
    connector = HttpConnector(base_url="https://a.example/v1")

    # Act
    digest = content_hash(connector)

    # Assert
    assert digest.startswith("sha256:")
    assert ":unhashable:" not in digest


def test_hash_inside_a_literal_mapping_is_identity_keyed() -> None:
    # Arrange — config_values_hash hashes a dict of literals, not the bare value.
    endpoint_a = HttpConnector(base_url="https://a.example/v1")
    endpoint_b = HttpConnector(base_url="https://b.example/v1")

    # Act
    hash_a = content_hash({"connector": endpoint_a})
    hash_b = content_hash({"connector": endpoint_b})

    # Assert
    assert hash_a != hash_b


def test_audit_dict_output_is_unchanged(sentinel_secret: str) -> None:
    # Arrange
    connector = HttpConnector(
        base_url="https://a.example/v1",
        credential=CredentialRef(secret=sentinel_secret),
    )

    # Act
    audit = connector._pirn_audit_dict()

    # Assert
    assert audit == {"connector": "HttpConnector", "has_credential": True}


def test_no_credential_appears_in_canonical_audit_or_hashed_form(sentinel_secret: str) -> None:
    # Arrange
    connector = HttpConnector(
        base_url="https://a.example/v1",
        credential=CredentialRef(secret=sentinel_secret),
    )

    # Act
    forms = [
        json.dumps(connector.__pirn_canonical__()),
        json.dumps(connector._pirn_audit_dict()),
        content_hash(connector),
        content_hash({"connector": connector}),
    ]

    # Assert
    assert all(sentinel_secret not in form for form in forms)
