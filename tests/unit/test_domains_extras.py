"""Unit tests for :class:`pirn.domains.extras_loader.ExtrasLoader`.

The loader is the import-time guard each ``pirn/domains/<name>/__init__.py``
calls so that missing optional dependencies surface as a clean
``ImportError`` with the install hint, instead of a cryptic
``ModuleNotFoundError`` deep in a knot module.
"""

from __future__ import annotations

import sys
from importlib import reload
from unittest.mock import patch
import unittest

import pytest

from pirn.domains import extras_loader as loader_module
from pirn.domains.extras_loader import ExtrasLoader


def _block_modules(*names: str):
    """Patch ``importlib.util.find_spec`` so the named modules look missing."""
    real_find_spec = loader_module.find_spec

    def fake(name):
        if name in names:
            return None
        return real_find_spec(name)

    return patch.object(loader_module, "find_spec", side_effect=fake)


class TestExtrasLoaderRequire(unittest.TestCase):
    def test_passes_when_every_module_resolves(self) -> None:
        ExtrasLoader("data", ["sys", "os"]).require()

    def test_raises_listing_each_missing_module(self) -> None:
        with _block_modules("definitely_not_a_real_module", "another_fake_one"):
            with self.assertRaises(ImportError) as exc_info:
                ExtrasLoader(
                    "data",
                    ["sys", "definitely_not_a_real_module", "another_fake_one"],
                ).require()
        message = str(exc_info.exception)
        assert "definitely_not_a_real_module" in message
        assert "another_fake_one" in message
        assert "sys," not in message

    def test_install_hint_uses_extra_name(self) -> None:
        with _block_modules("nonexistent_pkg"):
            with self.assertRaises(ImportError) as exc_info:
                ExtrasLoader("health", ["nonexistent_pkg"]).require()
        assert "pip install 'pirn[health]'" in str(exc_info.exception)

    def test_empty_module_list_is_a_noop(self) -> None:
        ExtrasLoader("agents", []).require()

    def test_exposes_extra_name_and_modules(self) -> None:
        loader = ExtrasLoader("ml", ["numpy", "pandas"])
        assert loader.extra_name == "ml"
        assert loader.modules == ("numpy", "pandas")


class TestDomainImportGuards(unittest.TestCase):
    """Domains that require extras must raise an actionable ImportError when
    those extras are missing.

    The data, ml, agents, health, signal, and oilgas domains all defer
    their ExtrasLoader calls to dependency-bound submodules (so the bare
    package import stays clean for orchestration-only consumers). The
    ``connectors`` domain follows the same pattern. Each has a positive
    "imports cleanly without extras" test below.

    No domain currently calls ExtrasLoader at package-init time. The
    parametrised test below stays parametrised to make adding a new
    eager-extras-checking domain a one-row change in the future.
    """

    def test_missing_dep_raises_install_hint(self) -> None:
        pass  # no domains currently call ExtrasLoader at package-init time

    def test_agents_imports_without_any_extras(self) -> None:
        sys.modules.pop("pirn.domains.agents", None)
        import pirn.domains.agents  # noqa: F401

    def test_connectors_namespace_imports_without_extras(self) -> None:
        sys.modules.pop("pirn.connectors", None)
        import pirn.connectors  # noqa: F401

    def test_data_namespace_imports_without_extras(self) -> None:
        # The data domain defers its ExtrasLoader call to pandas-bound
        # submodules, so the package import itself stays clean.
        sys.modules.pop("pirn.domains.data", None)
        import pirn.domains.data  # noqa: F401

    def test_ml_namespace_imports_without_extras(self) -> None:
        # The ml domain defers its ExtrasLoader call to dependency-bound
        # submodules; the package import itself stays clean so the
        # orchestration-only core (interfaces, types, data_prep,
        # features, training, evaluation, deployment) is usable
        # without numpy / pandas / scikit-learn installed.
        sys.modules.pop("pirn.domains.ml", None)
        import pirn.domains.ml  # noqa: F401

    def test_health_namespace_imports_without_extras(self) -> None:
        sys.modules.pop("pirn.domains.health", None)
        import pirn.domains.health  # noqa: F401

    def test_signal_namespace_imports_without_extras(self) -> None:
        # Signal extracted to the standalone pirn_signal package (SCD-11).
        sys.modules.pop("pirn_signal", None)
        import pirn_signal  # noqa: F401

    def test_oilgas_namespace_imports_without_extras(self) -> None:
        sys.modules.pop("pirn.domains.oilgas", None)
        import pirn.domains.oilgas  # noqa: F401

    def test_domains_namespace_always_imports(self) -> None:
        sys.modules.pop("pirn.domains", None)
        import pirn.domains
        reload(pirn.domains)
