"""``RateLimitError`` — the provider signalled HTTP 429 (rate limited)."""

from __future__ import annotations

from pirn_agents.llm.llm_provider_error import LLMProviderError


class RateLimitError(LLMProviderError):
    """Raised when the provider returns HTTP 429.

    Handled distinctly from other errors: the retry loop honours a
    server-supplied ``retry_after`` delay (from the ``Retry-After`` header)
    when present, falling back to the policy's jittered backoff otherwise.

    Parameters
    ----------
    message:
        Human-readable detail.
    retry_after:
        Server-requested delay before retrying, in seconds, or ``None`` when
        the response carried no ``Retry-After`` header.
    status_code:
        The HTTP status code (always ``429``).
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        status_code: int = 429,
    ) -> None:
        super().__init__(message)
        self.retry_after: float | None = retry_after
        self.status_code: int = status_code
