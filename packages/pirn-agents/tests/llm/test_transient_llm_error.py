"""Unit tests for :class:`pirn_agents.llm.transient_llm_error.TransientLLMError`."""

from __future__ import annotations

import unittest

from pirn_agents.llm.transient_llm_error import TransientLLMError


class TestTransientLLMError(unittest.TestCase):
    def test_defaults(self) -> None:
        error = TransientLLMError("network reset")
        assert error.status_code is None

    def test_carries_status_code(self) -> None:
        error = TransientLLMError("server error", status_code=503)
        assert error.status_code == 503


if __name__ == "__main__":
    unittest.main()
