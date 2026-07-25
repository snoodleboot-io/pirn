"""``CredentialRef`` — an opaque holder for a secret credential value.

A :class:`CredentialRef` wraps a single secret (api key, token, DSN) so it can
travel through the pirn graph without ever entering the content-addressed hash.
The whole point of this type is that two references holding *different* secrets
serialise identically: :meth:`_pirn_audit_dict` returns a constant redacted
token, so the secret contributes nothing to the hash and audit output stays
stable across differing credentials.

Access to the underlying secret is deliberately explicit and greppable via
:meth:`reveal`; the secret never appears in ``repr`` either.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class CredentialRef(PirnOpaqueValue):
    """A frozen, opaque wrapper around a single secret credential value.

    Attributes
    ----------
    secret:
        The raw credential value (api key, token, DSN). Never serialised,
        never rendered in ``repr``; read explicitly via :meth:`reveal`.
    """

    secret: str

    def reveal(self) -> str:
        """Return the underlying secret.

        Explicit, greppable access is the only way to obtain the secret, so
        no code path can accidentally serialise it.
        """
        return self.secret

    def _pirn_audit_dict(self) -> Any:
        """Return a constant redacted token independent of :attr:`secret`.

        Two ``CredentialRef`` values with different secrets produce identical
        audit output, keeping the secret out of the content-addressed hash and
        the hash contribution stable across differing credentials.
        """
        return "<CredentialRef:redacted>"

    def __repr__(self) -> str:
        """Return a secret-free representation."""
        return "CredentialRef(secret=<redacted>)"
