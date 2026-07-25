"""Unit tests for :class:`pirn_agents.llm.llm_provider_error.LLMProviderError`."""

from __future__ import annotations

import unittest

from pirn_agents.llm.llm_http_status_error import LLMHTTPStatusError
from pirn_agents.llm.llm_provider_error import LLMProviderError
from pirn_agents.llm.rate_limit_error import RateLimitError
from pirn_agents.llm.transient_llm_error import TransientLLMError


class TestLLMProviderError(unittest.TestCase):
    def test_is_an_exception(self) -> None:
        assert issubclass(LLMProviderError, Exception)

    def test_subclasses_share_the_base(self) -> None:
        for cls in (RateLimitError, TransientLLMError, LLMHTTPStatusError):
            assert issubclass(cls, LLMProviderError)

    def test_base_can_be_raised_and_caught(self) -> None:
        with self.assertRaises(LLMProviderError):
            raise LLMProviderError("boom")


if __name__ == "__main__":
    unittest.main()
