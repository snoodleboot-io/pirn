"""Content-hash identity of :class:`ConnectorBase` (PIR-848, PIR-852).

A connector's audit form is a secret-free per-class constant
(``{connector, has_credential}``).  Before PIR-848 that constant was also its
content hash, so two connectors of one class aimed at different endpoints
hashed equal and replay served one's recording to the other.  These tests pin
the fix: the hash is keyed on the instance (never on its configuration, and
never on a reusable address), the audit form is untouched, and no credential
reaches the canonical form.
"""

from __future__ import annotations

import json
import re

import pytest

from pirn.connectors.connector_base import ConnectorBase
from pirn.connectors.http_connector import HttpConnector
from pirn.core.hashing import content_hash
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.security.credential_ref import CredentialRef
from tests.unit.core.identity_reuse_subprocess import IdentityReuseSubprocess


@pytest.fixture
def sentinel_secret() -> str:
    """A recognisable secret the credential-safety tests search for."""
    return "sk-PIR848-SENTINEL-SECRET"


def test_live_connectors_with_different_endpoints_hash_differently() -> None:
    # Arrange
    endpoint_a = HttpConnector(base_url="https://a.example/v1")
    endpoint_b = HttpConnector(base_url="https://b.example/v1")

    # Act
    hash_a = content_hash(endpoint_a)
    hash_b = content_hash(endpoint_b)

    # Assert
    assert hash_a != hash_b


def test_identically_configured_separate_connectors_hash_differently() -> None:
    # Arrange — the intended identity semantics: equal config, two objects.
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


def test_canonical_form_is_the_hardened_opaque_identity_token() -> None:
    # Arrange
    connector = HttpConnector(base_url="https://a.example/v1")

    # Act
    canonical = connector.__pirn_canonical__()

    # Assert
    assert canonical == PirnOpaqueValue._pirn_audit_dict(connector)
    assert canonical == f"<HttpConnector@{connector._pirn_identity_token()}>"
    assert re.fullmatch(r"<HttpConnector@[0-9a-f]{32}>", canonical)


def test_hash_is_a_comparable_digest_not_the_unhashable_marker() -> None:
    # Arrange
    connector = HttpConnector(base_url="https://a.example/v1")

    # Act
    digest = content_hash(connector)

    # Assert
    assert digest.startswith("sha256:")
    assert ":unhashable:" not in digest


def test_connectors_inside_a_literal_mapping_hash_differently() -> None:
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


def test_no_credential_or_configuration_appears_in_the_canonical_form(
    sentinel_secret: str,
) -> None:
    # Arrange
    connector = HttpConnector(
        base_url="https://a.example/v1",
        credential=CredentialRef(secret=sentinel_secret),
    )

    # Act — the canonical form and the token are what content_hash consumes.
    canonical = json.dumps(connector.__pirn_canonical__())
    token = connector._pirn_identity_token()

    # Assert
    for form in (canonical, token):
        assert sentinel_secret not in form
        assert "a.example" not in form


def test_freed_connector_hash_never_reappears_for_a_new_connector_at_its_address() -> None:
    # Arrange — same class, same audit form, different credential; A is freed
    # and collected before B is built. Runs in a clean interpreter, where B
    # reliably lands at A's address (a coverage-traced suite heap stops reuse).

    # Act
    tally = IdentityReuseSubprocess.run("connector_hash", 200)

    # Assert — the loop only proves something if addresses were really reused.
    assert tally["reuses"] > 0, f"no address was reused; the loop tested nothing: {tally}"
    assert tally["collisions"] == 0, tally
