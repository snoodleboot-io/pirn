"""``RetryClassification`` — whether a failed call is safe to retry."""

from __future__ import annotations

from enum import Enum


class RetryClassification(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """Whether an error may be retried without risking a duplicate side effect.

    String-valued for stable, human-readable serialisation independent of enum
    ordering.

    Members
    -------
    SAFE:
        A transient failure (timeout, 5xx, connection/network error) where the
        request likely did not take effect; retrying — with the same idempotency
        key — is appropriate.
    UNSAFE:
        A failure that either won't improve on retry (validation / 4xx) or may
        have already applied a side effect; the call must not be retried blindly.
    """

    SAFE = "safe"
    UNSAFE = "unsafe"
