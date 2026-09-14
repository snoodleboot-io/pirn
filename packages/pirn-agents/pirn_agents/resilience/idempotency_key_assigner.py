# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``IdempotencyKeyAssigner`` — derive caller-stable idempotency keys.

ADR agents-speaks-core WS2 part 2 — **breaking key-format change, sanctioned**:
derivation now goes through :meth:`pirn.core.content_hasher.ContentHasher.hash` (``strict=True``)
instead of the former ``CanonicalJson``. The ``sha256:``-prefixed digest core
emits IS the format version; a key issued after this upgrade never matches
one issued before it for the same call. **An operator upgrading must drain
in-flight idempotent requests before/during the deploy** — a retry that lands
after the upgrade computes a different key than its first attempt registered,
so the backend sees a new operation and applies the mutation twice. See
"Idempotency keys" in ``docs/domains/agents.md`` for the operational note.

``ContentHasher.hash`` has no repr-based fallback for a value with no canonical form
(no ``__pirn_canonical__``, no pydantic core schema) — unlike the
``OpaquePolicy`` policies the former ``CanonicalJson`` supported, it either
hashes a value structurally or (``strict=True``) raises. An argument
``ContentHasher.hash`` cannot canonicalise but
whose ``repr`` is content-derived (``datetime``, ``UUID``, ``Decimal``, a
domain value object with its own ``__repr__``, ...) is still supported here:
:meth:`_normalise` walks ``arguments`` and, at each leaf ``ContentHasher.hash`` itself
would reject, falls back to that leaf's ``repr()`` — refusing one whose ``repr``
is the default identity form, mirroring the PIR-785/PIR-795 guard
the former ``OpaquePolicy.REPR_CONTENT`` used
to enforce, so this cannot key on a memory address either. Any leaf
``ContentHasher.hash`` already hashes structurally (primitives, mappings, sequences,
pydantic-aware types) passes through unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.content_hasher import ContentHasher
from pirn.exceptions.unhashable_value_error import UnhashableValueError

from pirn_agents._internal.json_shape import JsonShape


class IdempotencyKeyAssigner:
    """Assign a stable idempotency key to a (possibly retried) mutating call.

    A caller that already holds a stable key (e.g. a request id it will reuse
    across retries) passes it through unchanged. Otherwise the assigner *derives*
    one deterministically from the operation name and its arguments, so the same
    logical call always yields the same key — the property a backend needs to
    dedupe a retried mutation. The derivation canonicalises arguments via
    :meth:`pirn.core.content_hasher.ContentHasher.hash`, so key equality does not depend on
    mapping order.
    """

    def __init__(self, *, namespace: str = "") -> None:
        """Configure the assigner.

        Args:
            namespace: Optional prefix prepended (as ``"{namespace}:"``) to
                *derived* keys, to scope them per tenant/run. Caller-supplied
                keys are passed through verbatim and are never namespaced.
        """
        self._namespace = namespace

    def assign(
        self,
        *,
        operation: str,
        arguments: Mapping[str, Any],
        caller_key: str | None = None,
    ) -> str:
        """Return the idempotency key for a call.

        Args:
            operation: Stable name of the mutating operation.
            arguments: The call's arguments, canonicalised for the derived key.
            caller_key: A caller-supplied stable key; when a non-empty string,
                it is returned unchanged (caller-stable pass-through).

        Returns:
            The caller's key, or a deterministic derived key.

        Raises:
            TypeError: If ``arguments`` is not a mapping, or ``caller_key`` is
                neither a string nor ``None``.
            ValueError: If ``caller_key`` is an empty string.
        """
        if caller_key is not None:
            if not isinstance(caller_key, str):
                raise TypeError(
                    f"IdempotencyKeyAssigner: caller_key must be a str or None, "
                    f"got {type(caller_key).__name__}"
                )
            if not caller_key:
                raise ValueError("IdempotencyKeyAssigner: caller_key must be non-empty")
            return caller_key
        if not isinstance(arguments, Mapping):
            raise TypeError(
                f"IdempotencyKeyAssigner: arguments must be a Mapping, "
                f"got {type(arguments).__name__}"
            )
        normalised = self._normalise({"operation": operation, "arguments": arguments})
        digest = ContentHasher.hash(normalised, strict=True)
        return f"{self._namespace}:{digest}" if self._namespace else digest

    @classmethod
    def _normalise(cls, value: Any) -> Any:
        """Recursively replace an opaque leaf with its content-derived ``repr()``.

        Descends into mappings and sequences (the shapes ``ContentHasher.hash``
        also decomposes) so only the specific leaf that defeats
        canonicalisation is replaced — the rest of ``arguments`` keeps
        hitting ``ContentHasher.hash``'s normal structural hashing. A leaf is
        "opaque" here exactly when ``ContentHasher.hash(leaf, strict=True)`` would
        itself raise; probing with the real function (rather than
        re-implementing its type dispatch) is what keeps this from silently
        drifting out of step with what ``ContentHasher.hash`` can and cannot
        canonicalise on its own.

        Raises:
            TypeError: If an opaque leaf's ``repr`` is the default
                ``object.__repr__`` identity form — it renders a memory
                address, not content, so a retry could never derive the same
                key from an equal-but-distinct instance.
        """
        if JsonShape.is_any_mapping(value):
            return {k: cls._normalise(v) for k, v in value.items()}
        if JsonShape.is_list_or_tuple(value):
            return [cls._normalise(v) for v in value]
        try:
            ContentHasher.hash(value, strict=True)
        except UnhashableValueError:
            pass
        else:
            return value
        rendered = repr(value)
        if rendered == object.__repr__(value):
            raise TypeError(
                f"IdempotencyKeyAssigner: refusing an argument of type "
                f"{type(value).__name__}; it renders as {rendered!r}, which is "
                f"its memory address rather than its content, so a retry would "
                f"derive a different key than the original call."
            )
        return rendered
