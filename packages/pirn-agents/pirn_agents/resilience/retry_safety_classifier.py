"""``RetrySafetyClassifier`` — decide if a failed call may be safely retried.

Provider-neutral: rather than importing any backend's exception types, it
duck-types on a ``status_code`` attribute (as most HTTP client errors expose)
and falls back to a configurable set of transient exception classes. Timeouts,
connection/network errors, ``429`` throttling, and ``5xx`` server errors are
safe to retry; validation and other ``4xx`` client errors — which won't improve
on retry and may signal a side-effect risk — are not. Anything unrecognised is
conservatively unsafe, so an unknown failure on a mutating call is never blindly
retried. The verdict is a ``bool`` (:meth:`RetrySafetyClassifier.is_safe`): a
retry-safety decision about an error, not an outcome of the call.
"""

from __future__ import annotations

from collections.abc import Iterable


class RetrySafetyClassifier:
    """Classify an exception as safe or unsafe to retry, provider-neutrally."""

    def __init__(
        self,
        *,
        safe_exceptions: tuple[type[BaseException], ...] = (
            TimeoutError,
            ConnectionError,
            OSError,
        ),
        safe_status_codes: Iterable[int] = (408, 425, 429),
    ) -> None:
        """Configure the transient-error taxonomy.

        Args:
            safe_exceptions: Exception classes treated as transient (safe to
                retry) when no ``status_code`` is present.
            safe_status_codes: Explicit status codes treated as safe in addition
                to the whole ``5xx`` range. Defaults to the retryable ``4xx``
                codes (request timeout, too-early, too-many-requests).

        Raises:
            TypeError: If ``safe_exceptions`` holds a non-exception type.
        """
        for exc_type in safe_exceptions:
            if not (isinstance(exc_type, type) and issubclass(exc_type, BaseException)):
                raise TypeError(
                    f"RetrySafetyClassifier: safe_exceptions must be exception types, "
                    f"got {exc_type!r}"
                )
        self._safe_exceptions = tuple(safe_exceptions)
        self._safe_status_codes = frozenset(safe_status_codes)

    def is_safe(self, error: BaseException) -> bool:
        """Return whether ``error`` may be retried without risking a duplicate side effect.

        A present integer ``status_code`` takes precedence (``5xx`` or a
        configured safe code → safe, any other → unsafe); otherwise the
        exception type is matched against the transient set. Anything
        unrecognised is conservatively unsafe.
        """
        # getattr: dynamic probe over heterogeneous third-party exception attrs (no
        # shared declared type) — any HTTP-client error exposing an int status_code,
        # not just pirn's own LLMHTTPStatusError, participates in this taxonomy.
        status = getattr(error, "status_code", None)
        if isinstance(status, int) and not isinstance(status, bool):
            return 500 <= status <= 599 or status in self._safe_status_codes
        return isinstance(error, self._safe_exceptions)
