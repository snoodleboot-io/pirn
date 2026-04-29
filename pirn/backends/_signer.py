"""HMAC-SHA256 payload signing for DataStore backends.

Prevents insecure deserialization of tampered payloads (security finding C-1).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os


class _Signer:
    """Signs and verifies cloudpickle payloads with HMAC-SHA256.

    The digest size is fixed at 32 bytes by the SHA256 algorithm.
    """

    __digest_size = 32

    def __init__(self, key: bytes) -> None:
        self.__key = key

    @classmethod
    def from_env(cls, var: str = "PIRN_SIGNING_KEY") -> "_Signer":
        """Construct a _Signer from a base64-encoded key in an environment variable.

        Raises ``ValueError`` if the variable is unset or empty.

        Example::

            import secrets, base64
            key_b64 = base64.b64encode(secrets.token_bytes(32)).decode()
            # Set PIRN_SIGNING_KEY=<key_b64> in your environment, then:
            store = LocalDiskDataStore("/data", signer=_Signer.from_env())
        """
        raw = os.environ.get(var)
        if not raw:
            raise ValueError(
                f"Environment variable {var!r} is not set or empty. "
                "Set it to a base64-encoded signing key before constructing a signed DataStore."
            )
        return cls(base64.b64decode(raw))

    def sign(self, payload: bytes) -> bytes:
        """Prepend a 32-byte HMAC-SHA256 signature to payload."""
        sig = hmac.new(self.__key, payload, hashlib.sha256).digest()
        return sig + payload

    def verify(self, payload: bytes) -> bytes:
        """Verify the HMAC-SHA256 signature and return the raw payload.

        Raises ``ValueError`` if the payload is too short or the signature
        does not match.
        """
        if len(payload) < self.__digest_size:
            raise ValueError(
                "payload too short to contain a signature — possible tampering"
            )
        sig, raw = payload[: self.__digest_size], payload[self.__digest_size :]
        expected = hmac.new(self.__key, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError(
                "HMAC signature mismatch — payload may have been tampered with"
            )
        return raw
