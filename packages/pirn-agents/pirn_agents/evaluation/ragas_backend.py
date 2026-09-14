"""Lazy loader for the optional RAGAS metric backend (flat ``ragas`` extra).

The RAG metrics in this subpackage are self-contained and provider-neutral: they
need only a pluggable judge/embedding provider and pull in no third-party
evaluation library at import time. Teams that already standardise on the RAGAS
reference implementation can load it here to cross-check or delegate scoring; the
import is deferred through :meth:`~pirn_agents._internal.optional_import.OptionalImport.require` so ``import
pirn_agents`` — and importing this subpackage — stays backend-free.

Install the backend with ``pip install "pirn-agents[ragas]"``.
"""

from __future__ import annotations

from types import ModuleType

from pirn_agents._internal.optional_import import OptionalImport


class RagasBackend:
    """Namespace for the lazy optional-``ragas``-backend loader."""

    @staticmethod
    def load() -> ModuleType:
        """Import and return the optional ``ragas`` backend module.

        Returns:
            The imported ``ragas`` module.

        Raises:
            ImportError: If ``ragas`` is not installed. The message names the
                exact command ``pip install "pirn-agents[ragas]"``.
        """
        return OptionalImport.require("ragas", "ragas")
