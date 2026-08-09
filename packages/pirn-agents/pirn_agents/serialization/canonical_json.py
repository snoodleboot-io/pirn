"""``CanonicalJson`` — the package's single canonical JSON encoding and digest."""

from __future__ import annotations

import hashlib
import json
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
    :func:`~pirn_agents.determinism.content_digest.content_digest` already
    produce, so adopting the seam moves nothing already persisted.

    The single per-caller decision is
    :class:`~pirn_agents.serialization.opaque_policy.OpaquePolicy`, which
    defaults to refusing values JSON cannot represent.
    """

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
        if not isinstance(policy, OpaquePolicy):
            raise TypeError(
                f"CanonicalJson.encode: policy must be an OpaquePolicy, got {type(policy).__name__}"
            )
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=policy.fallback())

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
        return hashlib.sha256(cls.encode(payload, policy=policy).encode("utf-8")).hexdigest()
