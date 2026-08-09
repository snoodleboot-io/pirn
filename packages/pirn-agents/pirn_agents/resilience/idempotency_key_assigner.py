"""``IdempotencyKeyAssigner`` — derive caller-stable idempotency keys."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.serialization.canonical_json import CanonicalJson
from pirn_agents.serialization.opaque_policy import OpaquePolicy


class IdempotencyKeyAssigner:
    """Assign a stable idempotency key to a (possibly retried) mutating call.

    A caller that already holds a stable key (e.g. a request id it will reuse
    across retries) passes it through unchanged. Otherwise the assigner *derives*
    one deterministically from the operation name and its arguments, so the same
    logical call always yields the same key — the property a backend needs to
    dedupe a retried mutation. The derivation canonicalises arguments via
    sorted-key JSON, so key equality does not depend on mapping order.
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
        # OpaquePolicy.REPR rather than the seam's RAISE default, to keep
        # already-issued keys valid. NOTE: this carries the PIR-785 hazard --
        # an argument whose type has no content-derived __repr__ keys on its
        # memory address, so the retry that this key exists to dedupe derives a
        # *different* key and the mutation is applied twice. Tightening it
        # invalidates keys a backend may still be holding, so it needs its own
        # ticket rather than riding along with a canonicalisation collapse.
        digest = CanonicalJson.digest(
            {"operation": operation, "arguments": arguments}, policy=OpaquePolicy.REPR
        )
        return f"{self._namespace}:{digest}" if self._namespace else digest
