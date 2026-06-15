"""ATDD for Phase 2 (SCD-08 / SCD-09): the two pure-abstract provider bases live
in ``pirn.core.providers`` and their former domain locations no longer exist.

Relocating the bases is what breaks the ``agents -> ml`` and ``health -> agents``
edges; per convention there is **no re-export shim** at the old paths, so a stale
import must fail loudly rather than silently resolve.
"""

from __future__ import annotations

import importlib
import unittest


class TestProviderBasesResolveFromCore(unittest.TestCase):
    def test_embedding_provider_canonical_module(self) -> None:
        from pirn.core.providers.embedding_provider import EmbeddingProvider

        self.assertEqual(EmbeddingProvider.__module__, "pirn.core.providers.embedding_provider")

    def test_llm_provider_canonical_module(self) -> None:
        from pirn.core.providers.llm_provider import LLMProvider

        self.assertEqual(LLMProvider.__module__, "pirn.core.providers.llm_provider")

    def test_bases_subclass_pirn_opaque_value(self) -> None:
        from pirn.core.pirn_opaque_value import PirnOpaqueValue
        from pirn.core.providers.embedding_provider import EmbeddingProvider
        from pirn.core.providers.llm_provider import LLMProvider

        self.assertTrue(issubclass(EmbeddingProvider, PirnOpaqueValue))
        self.assertTrue(issubclass(LLMProvider, PirnOpaqueValue))


class TestOldPathsAreGone(unittest.TestCase):
    def test_embedding_provider_old_module_removed(self) -> None:
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("pirn.domains.ml.embedding_provider")

    def test_llm_provider_old_module_removed(self) -> None:
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("pirn_agents.llm_provider")


if __name__ == "__main__":
    unittest.main()
