"""HMAC-SHA256 signing helpers for pickle payloads.

Used by all DataStore backends to prevent insecure deserialization of
tampered payloads (security finding C-1).
"""

from __future__ import annotations

import hashlib as _hashlib
import hmac as _hmac

_SIG_LEN = 32  # HMAC-SHA256 produces 32 bytes


def sign(payload: bytes, key: bytes) -> bytes:
    """Prepend a 32-byte HMAC-SHA256 signature to *payload*."""
    sig = _hmac.new(key, payload, _hashlib.sha256).digest()
    return sig + payload


def verify(payload: bytes, key: bytes) -> bytes:
    """Verify the HMAC-SHA256 signature and return the raw payload.

    Raises ``ValueError`` if the payload is too short or the signature
    does not match (possible tampering).
    """
    if len(payload) < _SIG_LEN:
        raise ValueError(
            "payload too short to contain a signature — possible tampering"
        )
    sig, raw = payload[:_SIG_LEN], payload[_SIG_LEN:]
    expected = _hmac.new(key, raw, _hashlib.sha256).digest()
    if not _hmac.compare_digest(sig, expected):
        raise ValueError(
            "HMAC signature mismatch — payload may have been tampered with"
        )
    return raw
