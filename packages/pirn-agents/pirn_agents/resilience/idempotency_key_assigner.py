"""``IdempotencyKeyAssigner`` — derive caller-stable idempotency keys."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


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
        canonical = json.dumps(
            {"operation": operation, "arguments": arguments},
            sort_keys=True,
            separators=(",", ":"),
            default=repr,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{self._namespace}:{digest}" if self._namespace else digest
