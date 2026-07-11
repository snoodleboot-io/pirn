"""Unit tests for :class:`pirn_agents.llm.llm_http_status_error.LLMHTTPStatusError`."""

from __future__ import annotations

import unittest

from pirn_agents.llm.llm_http_status_error import LLMHTTPStatusError


class TestLLMHTTPStatusError(unittest.TestCase):
    def test_carries_status_code(self) -> None:
        error = LLMHTTPStatusError("bad request", status_code=400)
        assert error.status_code == 400

    def test_message_preserved(self) -> None:
        assert str(LLMHTTPStatusError("nope", status_code=404)) == "nope"


if __name__ == "__main__":
    unittest.main()
