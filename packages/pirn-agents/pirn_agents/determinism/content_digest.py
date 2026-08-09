"""``content_digest`` — a stable content hash for record/replay keying.

The cassette keys every LLM/tool/retrieval I/O by a digest of the *request*
payload, mirroring the content-addressed DAG (see
:meth:`pirn_agents.sessions.run_checkpoint.RunCheckpoint.content_hash`): identical
requests collapse to the same key, and any change to the payload yields a
different one. Time-travel diffing reuses the same digest to detect changed
inputs/outputs between two runs.

The canonicalisation lives in
:class:`~pirn_agents.serialization.canonical_json.CanonicalJson`, shared with
the cache, checkpoint and idempotency hashers.
"""

from __future__ import annotations

from typing import Any

from pirn_agents.serialization.canonical_json import CanonicalJson
from pirn_agents.serialization.opaque_policy import OpaquePolicy


def content_digest(payload: Any) -> str:
    """Return the SHA-256 hex digest of ``payload``'s canonical JSON form.

    Args:
        payload: Any JSON-serialisable value. Mapping keys are sorted and
            separators are tight so the digest is independent of key order and
            incidental whitespace. Non-JSON leaves fall back to ``str``.

    Returns:
        The 64-character hex SHA-256 digest of the canonical encoding.
    """
    # OpaquePolicy.STR rather than the seam's RAISE default: recorded cassettes
    # are keyed by digests taken with the `str` fallback, so tightening this
    # would orphan them. It carries the PIR-785 identity-keying hazard for
    # leaves that do not override __str__ -- a cassette recorded from such a
    # request can never be replayed, because the address will differ next run.
    # Tightening it is a cassette-format break and needs its own ticket.
    return CanonicalJson.digest(payload, policy=OpaquePolicy.STR)
