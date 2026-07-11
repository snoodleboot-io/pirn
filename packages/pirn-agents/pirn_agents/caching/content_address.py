"""Content-addressed cache keying: a stable hash over an arbitrary payload.

Mirrors how the DAG content-addresses node outputs — two calls with identical
inputs hash to the same key, so an idempotent tool call or embedding lookup
maps deterministically onto a cache entry. Non-JSON values fall back to
``repr`` so the keyer never raises on live objects; keys are order-independent
because mappings are serialised with sorted keys.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def content_address(payload: Any) -> str:
    """Return a stable 64-hex-char SHA-256 content address for ``payload``.

    Args:
        payload: Any JSON-ish value (mappings, sequences, scalars); non-JSON
            values are stringified via ``repr`` rather than raising.

    Returns:
        The hex SHA-256 digest of the canonical JSON encoding — identical for
        equal payloads, order-independent across mapping keys.
    """
    encoded = json.dumps(payload, sort_keys=True, default=repr, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()
