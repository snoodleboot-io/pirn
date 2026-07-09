"""Unit tests for the shared install-isolation gate's pirn-agents extensions.

The clean-venv *closure* check only works in CI (the dev venv has all seven
``pirn-*`` packages installed, so the closure assertion intentionally fails
here). These tests exercise the new backend-leak DETECTION logic directly,
independent of the resolved environment, so PIR-136's additive behavior is
covered without a clean venv.

The shared script lives at ``<repo>/scripts/check_install_isolation.py`` and is
NOT importable by name, so it is loaded by file path via importlib.
"""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _load_isolation_module() -> types.ModuleType:
    """Load the shared ``check_install_isolation`` script by file path.

    Walks up from this test file to the repo root (the directory that contains
    ``scripts/check_install_isolation.py``) and imports it via a
    file-location spec, so the test does not assume the script is importable
    by name.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "scripts" / "check_install_isolation.py"
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location(
                "_pirn_check_install_isolation", candidate
            )
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise AssertionError("could not locate scripts/check_install_isolation.py")


_ISO = _load_isolation_module()


class BackendDenylistSelectionTests(unittest.TestCase):
    """`_backend_denylist_for` picks the right denylist per package."""

    def test_pirn_core_keeps_original_backend_set(self) -> None:
        # The pirn-core code path must be byte-for-byte unaffected: the helper
        # returns the existing broad heavy-backend denylist for pirn-core.
        result = _ISO._backend_denylist_for("pirn-core")
        assert result is _ISO._BACKEND_DENYLIST
        assert "numpy" in result
        assert "torch" in result

    def test_unknown_package_falls_back_to_core_denylist(self) -> None:
        # Other domains are unchanged: they fall back to the core denylist.
        for pkg in ("pirn-signal", "pirn-data", "pirn-ml", "pirn-health", "pirn-oilgas"):
            assert _ISO._backend_denylist_for(pkg) is _ISO._BACKEND_DENYLIST

    def test_pirn_agents_forbids_connector_backends(self) -> None:
        result = _ISO._backend_denylist_for("pirn-agents")
        assert result == frozenset({"httpx", "openai", "anthropic", "qdrant_client", "mcp"})


class SubmoduleWalkLeakDetectionTests(unittest.TestCase):
    """`_check_no_backend_after_submodule_walk` flags leaked backends."""

    def _make_pkg(self, name: str) -> str:
        """Register a tiny, path-less synthetic package in ``sys.modules``.

        Path-less means ``walk_packages`` has no submodules to import, so the
        function's outcome is driven purely by what is already in
        ``sys.modules`` — exactly the leak condition under test.
        """
        module = types.ModuleType(name)
        # No __path__ attribute -> walk_packages iterates nothing.
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        return name

    def test_flags_leaked_backend_in_sys_modules(self) -> None:
        pkg = self._make_pkg("_synthetic_agents_pkg_leak")
        # Simulate a backend that leaked out of its lazy guard.
        fake_backend = "_synthetic_httpx"
        sys.modules[fake_backend] = types.ModuleType(fake_backend)
        self.addCleanup(sys.modules.pop, fake_backend, None)

        violations = _ISO._check_no_backend_after_submodule_walk(
            pkg, frozenset({fake_backend, "_synthetic_absent"})
        )

        assert len(violations) == 1
        assert fake_backend in violations[0]
        assert "must stay lazy" in violations[0]
        # An absent denylisted module must NOT be reported.
        assert "_synthetic_absent" not in violations[0]

    def test_clean_case_reports_no_violations(self) -> None:
        pkg = self._make_pkg("_synthetic_agents_pkg_clean")
        # None of the denylisted modules are present in sys.modules.
        violations = _ISO._check_no_backend_after_submodule_walk(
            pkg, frozenset({"_definitely_absent_backend_a", "_definitely_absent_backend_b"})
        )
        assert violations == []

    def test_missing_top_module_is_reported(self) -> None:
        violations = _ISO._check_no_backend_after_submodule_walk(
            "_module_that_does_not_exist_xyz", frozenset({"httpx"})
        )
        assert len(violations) == 1
        assert "_module_that_does_not_exist_xyz" in violations[0]
        assert "failed" in violations[0]


if __name__ == "__main__":
    unittest.main()
