"""Import-isolation guards for the extracted domain packages.

Each ``pirn_<domain>`` package must import cleanly with no optional extras
installed: the pure-Python orchestration layer (types and slim ``Knot``
stubs) stays importable, and heavy optional dependencies are imported
lazily by the modules that need them — so a bare ``import pirn_<domain>``
never raises on a missing extra.
"""

from __future__ import annotations

# cross-domain: skipped in per-package isolation, run by the unified suite (SCD-24)
import pytest as _pytest
_pytest.importorskip("pirn_agents")
pytestmark = _pytest.mark.cross_domain

import sys
import unittest
from importlib import reload


class TestDomainImportGuards(unittest.TestCase):
    """Every extracted domain (and the core ``pirn.connectors`` namespace)
    imports cleanly without any optional extras installed.

    Heavy dependencies are imported lazily by the dependency-bound
    submodules, so the bare package import stays clean for
    orchestration-only consumers.
    """

    def test_agents_imports_without_any_extras(self) -> None:
        sys.modules.pop("pirn_agents", None)
        import pirn_agents  # noqa: F401

    def test_connectors_namespace_imports_without_extras(self) -> None:
        sys.modules.pop("pirn.connectors", None)
        import pirn.connectors  # noqa: F401

    def test_data_namespace_imports_without_extras(self) -> None:
        # The data domain defers its heavy imports to pandas-bound
        # submodules, so the package import itself stays clean.
        sys.modules.pop("pirn_data", None)
        import pirn_data  # noqa: F401

    def test_ml_namespace_imports_without_extras(self) -> None:
        # The ml domain defers its heavy imports to dependency-bound
        # submodules; the package import itself stays clean so the
        # orchestration-only core (interfaces, types, data_prep,
        # features, training, evaluation, deployment) is usable
        # without numpy / pandas / scikit-learn installed.
        sys.modules.pop("pirn_ml", None)
        import pirn_ml  # noqa: F401

    def test_health_namespace_imports_without_extras(self) -> None:
        sys.modules.pop("pirn_health", None)
        import pirn_health  # noqa: F401

    def test_signal_namespace_imports_without_extras(self) -> None:
        # Signal extracted to the standalone pirn_signal package (SCD-11).
        sys.modules.pop("pirn_signal", None)
        import pirn_signal  # noqa: F401

    def test_oilgas_namespace_imports_without_extras(self) -> None:
        sys.modules.pop("pirn_oilgas", None)
        import pirn_oilgas  # noqa: F401

    def test_domains_namespace_always_imports(self) -> None:
        sys.modules.pop("pirn.domains", None)
        import pirn.domains

        reload(pirn.domains)
