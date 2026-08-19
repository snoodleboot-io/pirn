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
    # STR_CONTENT, not the seam's RAISE default and no longer the bare STR
    # (PIR-795). Recorded cassettes are keyed by digests taken with the `str`
    # fallback, and STR_CONTENT renders every leaf `str` already rendered as
    # content byte-identically -- datetime, UUID, Decimal, Path, Enum, and any
    # type with its own __str__ -- so no cassette that could be replayed moves.
    #
    # What it removes is the PIR-785 hazard: a leaf whose __str__ falls through
    # to the default __repr__ used to be digested by memory address, so the
    # cassette recorded from it could never replay -- the address differs next
    # run. That is now a TypeError at record time instead of a silent miss at
    # replay time. Nothing is orphaned, because a key that never reproduced was
    # never usable. RAISE would go further and reject the content-rendering
    # leaves too, which WOULD be a cassette-format break.
    return CanonicalJson.digest(payload, policy=OpaquePolicy.STR_CONTENT)
