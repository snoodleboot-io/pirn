"""Canonical JSON serialisation for content-addressed hashing (WS8 / PIR-726).

Several subsystems derive a stable id by hashing a payload's JSON encoding:
checkpoint ids (F14), cassette and trace keys (F29), cache keys (F27),
idempotency keys, and generated knot ids. Each grew its own ``json.dumps``
call, and the flags drifted apart — so two subsystems could disagree about
whether ``{"a": 1}`` is ``'{"a": 1}'`` or ``'{"a":1}'`` and hash to different
ids for the same content.

This subpackage owns the single answer:
:class:`~pirn_agents.serialization.canonical_json.CanonicalJson` encodes with
sorted keys, tight separators, ``ensure_ascii`` at its default and UTF-8, and
digests with SHA-256 to bare 64-hex. The one genuinely per-caller decision —
what to do with a leaf JSON cannot encode — is an explicit argument rather
than a buried flag: see
:class:`~pirn_agents.serialization.opaque_policy.OpaquePolicy`, which defaults
to refusing.

This is a hashing seam only. It is not a general serialisation framework, and
deliberately has no codec or ``Serializer`` base class.
"""

from __future__ import annotations

__all__: list[str] = []
