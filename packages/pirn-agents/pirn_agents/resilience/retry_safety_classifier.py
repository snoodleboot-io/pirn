"""``RetrySafetyClassifier`` — decide if a failed call may be safely retried.

Provider-neutral: rather than importing any backend's exception types, it
duck-types on a ``status_code`` attribute (as most HTTP client errors expose)
and falls back to a configurable set of transient exception classes. Timeouts,
connection/network errors, ``429`` throttling, and ``5xx`` server errors are
classified :attr:`RetryClassification.SAFE`; validation and other ``4xx`` client
errors — which won't improve on retry and may signal a side-effect risk — are
:attr:`RetryClassification.UNSAFE`. Anything unrecognised is conservatively
UNSAFE, so an unknown failure on a mutating call is never blindly retried.
"""

from __future__ import annotations

from collections.abc import Iterable

from pirn_agents.resilience.retry_classification import RetryClassification


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

    def classify(self, error: BaseException) -> RetryClassification:
        """Return whether ``error`` is safe or unsafe to retry.

        A present integer ``status_code`` takes precedence (``5xx`` or a
        configured safe code → SAFE, any other → UNSAFE); otherwise the
        exception type is matched against the transient set.
        """
        status = getattr(error, "status_code", None)
        if isinstance(status, int) and not isinstance(status, bool):
            if 500 <= status <= 599 or status in self._safe_status_codes:
                return RetryClassification.SAFE
            return RetryClassification.UNSAFE
        if isinstance(error, self._safe_exceptions):
            return RetryClassification.SAFE
        return RetryClassification.UNSAFE

    def is_safe(self, error: BaseException) -> bool:
        """Convenience predicate: ``True`` iff ``error`` classifies as SAFE."""
        return self.classify(error) is RetryClassification.SAFE
