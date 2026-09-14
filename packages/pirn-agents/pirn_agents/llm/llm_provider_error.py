"""``LLMProviderError`` — base class for LLM provider failures."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class LLMProviderError(PirnError):
    """Base class for every error raised by an LLM provider connector.

    Concrete subclasses distinguish rate limiting
    (:class:`pirn_agents.llm.rate_limit_error.RateLimitError`), transient
    server/network failures
    (:class:`pirn_agents.llm.transient_llm_error.TransientLLMError`), and
    non-retryable HTTP status errors
    (:class:`pirn_agents.llm.llm_http_status_error.LLMHTTPStatusError`).
    """
