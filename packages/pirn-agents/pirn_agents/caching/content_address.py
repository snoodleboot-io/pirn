"""Content-addressed cache keying: a stable hash over an arbitrary payload.

Mirrors how the DAG content-addresses node outputs — two calls with identical
inputs hash to the same key, so an idempotent tool call or embedding lookup
maps deterministically onto a cache entry. Keys are order-independent because
mappings are serialised with sorted keys.

The canonicalisation itself lives in
:class:`~pirn_agents.serialization.canonical_json.CanonicalJson`, shared with
the cassette, checkpoint and idempotency hashers so that every subsystem
agrees on what a payload's content address is.
"""

from __future__ import annotations

from typing import Any

from pirn_agents.serialization.canonical_json import CanonicalJson


def content_address(payload: Any) -> str:
    """Return a stable 64-hex-char SHA-256 content address for ``payload``.

    Args:
        payload: A JSON-encodable value (mappings, sequences, scalars).

    Returns:
        The hex SHA-256 digest of the canonical JSON encoding — identical for
        equal payloads, order-independent across mapping keys.

    Raises:
        TypeError: If ``payload`` contains a value JSON cannot represent.
            This used to fall back to ``repr`` so the keyer "never raised on
            live objects" (PIR-785). That was worse than raising: the default
            ``object.__repr__`` is built from the instance's memory address, so
            the key described *where the object sat*, not what it contained —
            and CPython hands a freed address straight back to the next
            allocation. Two hundred distinct requests collapsed onto seventeen
            keys, and :meth:`~pirn_agents.caching.result_cache.ResultCache.get_or_compute`
            answered one request with another's value, silently. Callers with a
            non-JSON payload must project it to JSON-encodable data first, so
            the key is derived from content the caller chose.
    """
    return CanonicalJson.digest(payload)
