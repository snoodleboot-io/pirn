"""Unit tests for :class:`CredentialRef`."""

from __future__ import annotations

import unittest

from pirn_agents.credential_ref import CredentialRef


class TestCredentialRef(unittest.TestCase):
    def test_audit_dict_is_stable_across_differing_secrets(self) -> None:
        # Arrange: two refs holding DIFFERENT secrets.
        ref_a = CredentialRef("secret-A")
        ref_b = CredentialRef("secret-B")

        # Act: obtain each ref's audit form (what feeds the content hash).
        audit_a = ref_a._pirn_audit_dict()
        audit_b = ref_b._pirn_audit_dict()

        # Assert: identical audit output => secret excluded from the hash.
        assert audit_a == audit_b
        assert "secret-A" not in str(audit_a)
        assert "secret-B" not in str(audit_b)

    def test_reveal_returns_the_secret(self) -> None:
        # Arrange
        ref = CredentialRef("top-secret")

        # Act / Assert
        assert ref.reveal() == "top-secret"

    def test_repr_redacts_the_secret(self) -> None:
        # Arrange
        ref = CredentialRef("top-secret")

        # Act
        text = repr(ref)

        # Assert: repr never leaks the secret.
        assert "top-secret" not in text
        assert "redacted" in text


if __name__ == "__main__":
    unittest.main()
