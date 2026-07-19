"""Guard: the provider bases no longer live in ``pirn.core`` (PIR-735).

Supersedes the former ``test_provider_relocation.py`` ATDD (SCD-08/SCD-09), which
locked the provider bases INTO core. The design was reversed: each consuming
domain now owns its own copy (``pirn_agents``/``pirn_health`` for ``LLMProvider``,
``pirn_agents``/``pirn_ml`` for ``EmbeddingProvider``), avoiding cross-domain
edges via duplication rather than centralisation. Per convention there is no
re-export shim, so a stale ``pirn.core.providers`` import must fail loudly.

This is a pure-core test — it imports no domain package.
"""

from __future__ import annotations

import importlib
import unittest


class TestProvidersRemovedFromCore(unittest.TestCase):
    def test_llm_provider_module_gone(self) -> None:
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("pirn.core.providers.llm_provider")

    def test_embedding_provider_module_gone(self) -> None:
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("pirn.core.providers.embedding_provider")

    def test_providers_package_gone(self) -> None:
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("pirn.core.providers")


if __name__ == "__main__":
    unittest.main()
