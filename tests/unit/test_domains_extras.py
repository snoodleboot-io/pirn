"""Unit tests for the domain-extras import-time guard.

Each ``pirn/domains/<name>/__init__.py`` calls :func:`pirn.domains._extras.require_extra`
with the module names its optional extras must provide. These tests verify the
guard surfaces a clean ``ImportError`` (with the install hint) when any required
module is missing, and stays silent when every module resolves.
"""

from __future__ import annotations

import sys
from importlib import reload
from unittest.mock import patch

import pytest

from pirn.domains import _extras


# ────────────────────────────────────────────────────────────────────── helpers


def _block_modules(*names: str):
    """Patch ``importlib.util.find_spec`` so the named modules look missing."""
    real_find_spec = _extras.find_spec

    def fake(name):
        if name in names:
            return None
        return real_find_spec(name)

    return patch.object(_extras, "find_spec", side_effect=fake)


# ───────────────────────────────────────────────────────────── require_extra()


class TestRequireExtra:
    def test_passes_when_every_module_resolves(self) -> None:
        # ``sys`` and ``os`` always exist; this should be a no-op.
        _extras.require_extra("data", ["sys", "os"])

    def test_raises_listing_each_missing_module(self) -> None:
        with _block_modules("definitely_not_a_real_module", "another_fake_one"):
            with pytest.raises(ImportError) as exc_info:
                _extras.require_extra(
                    "data",
                    ["sys", "definitely_not_a_real_module", "another_fake_one"],
                )
        msg = str(exc_info.value)
        assert "definitely_not_a_real_module" in msg
        assert "another_fake_one" in msg
        # The present module must NOT appear in the error.
        assert "sys," not in msg

    def test_install_hint_uses_extra_name(self) -> None:
        with _block_modules("nonexistent_pkg"):
            with pytest.raises(ImportError) as exc_info:
                _extras.require_extra("health", ["nonexistent_pkg"])
        assert "pip install 'pirn[health]'" in str(exc_info.value)

    def test_empty_module_list_is_a_noop(self) -> None:
        # The agents domain has no required extras — passing [] must succeed.
        _extras.require_extra("agents", [])


# ──────────────────────────────────────────────────────── per-domain guard


class TestDomainImportGuards:
    """Each domain must raise ImportError naming its extra when a dep is gone."""

    @pytest.mark.parametrize(
        ("domain", "blocked", "extra"),
        [
            ("data",   "pandas",  "data"),
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
        msg = str(exc_info.value)
        assert blocked in msg
        assert f"pip install 'pirn[{extra}]'" in msg

    def test_agents_imports_without_any_extras(self) -> None:
        # No required modules → must always import cleanly.
        sys.modules.pop("pirn.domains.agents", None)
        import pirn.domains.agents  # noqa: F401

    def test_connectors_namespace_imports_without_extras(self) -> None:
        # Connectors namespace itself has no top-level extras requirement.
        # Per-connector submodules will enforce their own extras when they land.
        sys.modules.pop("pirn.domains.connectors", None)
        import pirn.domains.connectors  # noqa: F401

    def test_domains_namespace_always_imports(self) -> None:
        sys.modules.pop("pirn.domains", None)
        import pirn.domains

        # Reloading must not introduce side effects.
        reload(pirn.domains)
