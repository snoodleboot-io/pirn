"""``content_digest`` — a stable content hash for record/replay keying.

The cassette keys every LLM/tool/retrieval I/O by a digest of the *request*
payload, mirroring the content-addressed DAG (see
:meth:`pirn_agents.sessions.run_checkpoint.RunCheckpoint.content_hash`): identical
requests collapse to the same key, and any change to the payload yields a
different one. Time-travel diffing reuses the same digest to detect changed
inputs/outputs between two runs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def content_digest(payload: Any) -> str:
    """Return the SHA-256 hex digest of ``payload``'s canonical JSON form.

    Args:
        payload: Any JSON-serialisable value. Mapping keys are sorted and
            separators are tight so the digest is independent of key order and
            incidental whitespace. Non-JSON leaves fall back to ``str``.

    Returns:
        The 64-character hex SHA-256 digest of the canonical encoding.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
