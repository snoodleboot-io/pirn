"""``LLMHTTPStatusError`` — a non-retryable HTTP error response."""

from __future__ import annotations

from pirn_agents.llm.llm_provider_error import LLMProviderError


class LLMHTTPStatusError(LLMProviderError):
    """Raised for a non-retryable HTTP error (a 4xx other than 429).

    These indicate a client-side problem (bad request, auth failure, missing
    model) that retrying cannot fix, so the retry loop propagates them
    immediately rather than backing off.

    Parameters
    ----------
    message:
        Human-readable detail.
    status_code:
        The HTTP status code that triggered the error.
    """

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code: int = status_code
