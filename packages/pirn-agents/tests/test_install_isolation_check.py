"""Unit tests for the shared install-isolation gate, run from pirn-agents.

The clean-venv *closure* check only works in CI (the dev venv has all seven
``pirn-*`` packages installed, so the closure assertion intentionally fails
here). These tests exercise the backend-leak DETECTION logic directly,
independent of the resolved environment, so the per-package denylist and the
submodule walk are covered without a clean venv.

The shared script lives at ``<repo>/scripts/check_install_isolation.py`` and is
not importable by name, so ``scripts/`` is put on ``sys.path`` and the module is
imported from there — it imports its own collaborators from ``gatekit``, which a
bare file-location import cannot resolve.
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


def _scripts_directory() -> Path:
    """The repository's ``scripts/`` directory, found by walking up from here."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "scripts" / "check_install_isolation.py"
        if candidate.is_file():
            return candidate.parent
    raise AssertionError("could not locate scripts/check_install_isolation.py")


sys.path.insert(0, str(_scripts_directory()))

from check_install_isolation import CheckInstallIsolation  # noqa: E402  # sys.path set just above


class BackendDenylistSelectionTests(unittest.TestCase):
    """`_backend_denylist_for` is the derived denylist minus the hard-dependency closure."""

    def test_every_package_allows_pirn_core_hard_dependency_numpy(self) -> None:
        # numpy is a pirn-core hard dependency, so it is hard for every package.
        for pkg in sorted(CheckInstallIsolation._expected_pirn_closure):
            result = CheckInstallIsolation._backend_denylist_for(pkg)
            assert "numpy" not in result
            assert result <= CheckInstallIsolation.backend_denylist()

    def test_pirn_agents_forbids_its_connector_backends(self) -> None:
        result = CheckInstallIsolation._backend_denylist_for("pirn-agents")
        assert {
            "httpx",
            "openai",
            "anthropic",
            "qdrant_client",
            "mcp",
            "sentence_transformers",
            "asyncpg",
            "pgvector",
            "chromadb",
            "neo4j",
            "kuzu",
            "aiosqlite",
            "aioboto3",
            "boto3",
            "opentelemetry",
            "outlines",
            "pypdf",
            "docx",
            "bs4",
            "ragas",
        } <= result

    def test_domain_packages_forbid_every_optional_backend(self) -> None:
        for pkg in ("pirn-signal", "pirn-data", "pirn-ml", "pirn-health", "pirn-oilgas"):
            result = CheckInstallIsolation._backend_denylist_for(pkg)
            assert {
                "pandas",
                "polars",
                "pyarrow",
                "scipy",
                "sklearn",
                "torch",
                "pydicom",
                "segyio",
            } <= result


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

        violations = CheckInstallIsolation._check_no_backend_after_submodule_walk(
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
        violations = CheckInstallIsolation._check_no_backend_after_submodule_walk(
            pkg, frozenset({"_definitely_absent_backend_a", "_definitely_absent_backend_b"})
        )
        assert violations == []

    def test_missing_top_module_is_reported(self) -> None:
        violations = CheckInstallIsolation._check_no_backend_after_submodule_walk(
            "_module_that_does_not_exist_xyz", frozenset({"httpx"})
        )
        assert len(violations) == 1
        assert "_module_that_does_not_exist_xyz" in violations[0]
        assert "failed" in violations[0]


if __name__ == "__main__":
    unittest.main()
