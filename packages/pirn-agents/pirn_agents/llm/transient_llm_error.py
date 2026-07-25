"""``TransientLLMError`` — a retryable server-side or network failure."""

from __future__ import annotations

from pirn_agents.llm.llm_provider_error import LLMProviderError


class TransientLLMError(LLMProviderError):
    """Raised for a transient, retryable failure.

    Covers HTTP 5xx responses and transport-level errors (connection resets,
    read/write/connect timeouts). The retry loop retries these with jittered
    exponential backoff until the policy's ``max_retries`` is exhausted.

    Parameters
    ----------
    message:
        Human-readable detail.
    status_code:
        The HTTP status code when the failure was an HTTP 5xx, or ``None`` for
        a transport-level error.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code: int | None = status_code
