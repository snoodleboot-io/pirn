"""``CanonicalJson`` — legacy canonical JSON encoding and digest (ADR agents-speaks-core WS2).

.. deprecated::
    The "agents speaks core" ADR (2026-09-13) retires this class in favour of
    :func:`pirn.core.hashing.content_hash`, which already produces the
    ``sha256:``-prefixed content hash every other pirn domain agrees on and
    honours a type's own :meth:`~pirn.core.pirn_opaque_value.PirnOpaqueValue._pirn_audit_dict`
    for opaque leaves instead of a caller-supplied fallback policy. **New call
    sites must call** ``content_hash`` **directly and must not use this
    class.**

    The actual cut-over of :meth:`digest` to ``content_hash`` is deliberately
    **not** made in this change: three existing callers persist or transmit
    the bare-hex digest this class produces today as a durable key —
    ``pirn_agents.resilience.idempotency_key_assigner.IdempotencyKeyAssigner``
    (a retry-dedup key sent to an external backend — moving it makes a retried
    mutation apply twice), ``pirn_agents.builder.agent_knot_id_factory.AgentKnotIdFactory``
    (a knot id embedded in lineage records and the engine's content-addressed
    cache), and ``pirn_agents.sessions.run_checkpoint.RunCheckpoint`` (a
    durable checkpoint id). None of those three lanes has a dual-read /
    key-rollover migration in place yet, so flipping the algorithm here today
    would silently double-apply retried mutations and orphan stored
    checkpoints/cache entries in production. That migration is a product
    decision for those lanes, not something this workstream can make safely
    on their behalf — see the WS2 report for the deferral.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from typing import Any

from pirn_agents.serialization.opaque_policy import OpaquePolicy


class CanonicalJson:
    """Encodes a payload to one fixed canonical JSON form, and digests it.

    Every content-addressed id in the package — checkpoint ids, cassette and
    trace keys, cache keys, idempotency keys, generated knot ids — is a SHA-256
    over a JSON encoding. Those encodings must agree, or two subsystems hash
    the same content to different ids.

    The canonical form is fixed and not configurable:

    * ``sort_keys=True`` — mapping order is not content, so it must not move
      the digest.
    * ``separators=(",", ":")`` — no incidental whitespace.
    * ``ensure_ascii`` at its default — non-ASCII is escaped. Flipping this to
      ``False`` would move the key of every payload containing non-ASCII text
      while leaving an ASCII-only golden test green: a storage break that
      passes CI and fails in production.
    * UTF-8 bytes, SHA-256, bare 64-hex output.

    This form is what
    :meth:`~pirn_agents.sessions.run_checkpoint.RunCheckpoint.content_hash` and
    :meth:`~pirn_agents.determinism.content_digest.ContentDigest.digest` already
    produce, so adopting the seam moves nothing already persisted.

    The single per-caller decision is
    :class:`~pirn_agents.serialization.opaque_policy.OpaquePolicy`, which
    defaults to refusing values JSON cannot represent — see that class for why
    it is itself legacy guidance rather than the ADR-aligned mechanism.

    .. deprecated::
        See the module docstring. Kept, unchanged in behaviour, for the
        existing durable-key callers; do not add new callers.
    """

    _deprecation_note = (
        "is deprecated (ADR agents-speaks-core WS2); prefer "
        "pirn.core.hashing.content_hash(payload) directly for new code, and "
        "give an opaque type a _pirn_audit_dict() instead of an OpaquePolicy "
        "fallback. This class is kept, byte-for-byte unchanged, only for "
        "callers whose persisted/transmitted keys (idempotency keys, "
        "checkpoint ids, generated knot ids) were derived from this exact "
        "algorithm and have not yet migrated."
    )

    @classmethod
    def encode(cls, payload: Any, *, policy: OpaquePolicy = OpaquePolicy.RAISE) -> str:
        """Return the canonical JSON text for ``payload``.

        Args:
            payload: A JSON-encodable value. Leaves JSON cannot represent are
                handled per ``policy``.
            policy: What to do with a non-JSON leaf. Defaults to
                :attr:`OpaquePolicy.RAISE`.

        Returns:
            The canonical JSON encoding — sorted keys, tight separators,
            non-ASCII escaped.

        Raises:
            TypeError: If ``policy`` is not an :class:`OpaquePolicy`, or if it
                is :attr:`OpaquePolicy.RAISE` and ``payload`` contains a leaf
                JSON cannot represent.
            ValueError: If ``payload`` contains a circular reference.
        """
        warnings.warn(
            f"CanonicalJson.encode {cls._deprecation_note}",
            DeprecationWarning,
            stacklevel=2,
        )
        return cls._encode_raw(payload, policy=policy, caller="encode")

    @classmethod
    def digest(cls, payload: Any, *, policy: OpaquePolicy = OpaquePolicy.RAISE) -> str:
        """Return the SHA-256 hex digest of ``payload``'s canonical encoding.

        Args:
            payload: A JSON-encodable value.
            policy: What to do with a non-JSON leaf. Defaults to
                :attr:`OpaquePolicy.RAISE`.

        Returns:
            A bare 64-character lowercase hex digest. Equal payloads yield
            equal digests regardless of mapping key order.

        Raises:
            TypeError: If ``policy`` is not an :class:`OpaquePolicy`, or if it
                is :attr:`OpaquePolicy.RAISE` and ``payload`` contains a leaf
                JSON cannot represent.
            ValueError: If ``payload`` contains a circular reference.
        """
        warnings.warn(
            f"CanonicalJson.digest {cls._deprecation_note}",
            DeprecationWarning,
            stacklevel=2,
        )
        encoded = cls._encode_raw(payload, policy=policy, caller="digest")
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _encode_raw(payload: Any, *, policy: OpaquePolicy, caller: str) -> str:
        """Return the canonical JSON text without emitting a deprecation warning.

        Shared by :meth:`encode` and :meth:`digest` so a single call into
        either public method emits exactly one warning, not two.
        """
        if not isinstance(policy, OpaquePolicy):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime-bound input; guard is deliberate
            raise TypeError(
                f"CanonicalJson.{caller}: policy must be an OpaquePolicy, got {type(policy).__name__}"
            )
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=policy.fallback())
