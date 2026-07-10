"""Unit tests for :class:`LLMProviderKnot`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.tapestry import Tapestry

from pirn_agents.llm_provider_knot import LLMProviderKnot
from tests.specializations.conftest import StubLLMProvider


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_provider_unchanged(self) -> None:
        provider = StubLLMProvider(["hello"])
        with Tapestry():
            k = LLMProviderKnot.__new__(LLMProviderKnot)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        result = await k.process(provider=provider)
        assert result is provider
        assert isinstance(result, LLMProvider)
