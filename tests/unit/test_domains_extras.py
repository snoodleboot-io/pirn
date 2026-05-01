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


class TestExtrasLoaderRequire:
    def test_passes_when_every_module_resolves(self) -> None:
        ExtrasLoader("data", ["sys", "os"]).require()

    def test_raises_listing_each_missing_module(self) -> None:
        with _block_modules("definitely_not_a_real_module", "another_fake_one"):
            with pytest.raises(ImportError) as exc_info:
                ExtrasLoader(
                    "data",
                    ["sys", "definitely_not_a_real_module", "another_fake_one"],
                ).require()
        message = str(exc_info.value)
        assert "definitely_not_a_real_module" in message
        assert "another_fake_one" in message
        assert "sys," not in message

    def test_install_hint_uses_extra_name(self) -> None:
        with _block_modules("nonexistent_pkg"):
            with pytest.raises(ImportError) as exc_info:
                ExtrasLoader("health", ["nonexistent_pkg"]).require()
        assert "pip install 'pirn[health]'" in str(exc_info.value)

    def test_empty_module_list_is_a_noop(self) -> None:
        ExtrasLoader("agents", []).require()

    def test_exposes_extra_name_and_modules(self) -> None:
        loader = ExtrasLoader("ml", ["numpy", "pandas"])
        assert loader.extra_name == "ml"
        assert loader.modules == ("numpy", "pandas")


class TestDomainImportGuards:
    """Domains that require extras must raise an actionable ImportError when
    those extras are missing. The data domain intentionally defers its
    ExtrasLoader call to the pandas-bound submodules, so it is excluded
    from this parametrised set."""

    @pytest.mark.parametrize(
        ("domain", "blocked", "extra"),
        [
            ("ml",     "numpy",   "ml"),
            ("health", "pydicom", "health"),
            ("signal", "scipy",   "signal"),
            ("oilgas", "segyio",  "oilgas"),
        ],
    )
    def test_missing_dep_raises_install_hint(
        self, domain: str, blocked: str, extra: str
    ) -> None:
        modname = f"pirn.domains.{domain}"
        sys.modules.pop(modname, None)
        with _block_modules(blocked):
            with pytest.raises(ImportError) as exc_info:
                __import__(modname)
        message = str(exc_info.value)
        assert blocked in message
        assert f"pip install 'pirn[{extra}]'" in message

    def test_agents_imports_without_any_extras(self) -> None:
        sys.modules.pop("pirn.domains.agents", None)
        import pirn.domains.agents  # noqa: F401

    def test_connectors_namespace_imports_without_extras(self) -> None:
        sys.modules.pop("pirn.domains.connectors", None)
        import pirn.domains.connectors  # noqa: F401

    def test_data_namespace_imports_without_extras(self) -> None:
        # The data domain defers its ExtrasLoader call to pandas-bound
        # submodules, so the package import itself stays clean.
        sys.modules.pop("pirn.domains.data", None)
        import pirn.domains.data  # noqa: F401

    def test_domains_namespace_always_imports(self) -> None:
        sys.modules.pop("pirn.domains", None)
        import pirn.domains
        reload(pirn.domains)
