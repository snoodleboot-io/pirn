"""Tests for the install-isolation gate's submodule walk and per-package denylist (PIR-872)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_install_isolation  # noqa: E402
from check_install_isolation import (  # noqa: E402
    _backend_denylist_for,
    _check_no_backend_after_submodule_walk,
)


def _package(tmp_path: Path, name: str, modules: dict[str, str]) -> None:
    root = tmp_path / name
    root.mkdir()
    (root / "__init__.py").write_text("")
    for module, source in modules.items():
        (root / f"{module}.py").write_text(source)


@pytest.fixture
def isolated_modules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.syspath_prepend(str(tmp_path))
    before = set(sys.modules)
    yield tmp_path
    for name in set(sys.modules) - before:
        sys.modules.pop(name, None)


def test_denylist_drops_backends_the_hard_dependency_closure_provides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        check_install_isolation, "_hard_dependency_closure", lambda _package: {"acme", "numpy"}
    )
    monkeypatch.setattr(
        check_install_isolation.importlib.metadata,
        "packages_distributions",
        lambda: {"numpy": ["numpy"], "pandas": ["pandas"]},
    )

    denylist = _backend_denylist_for("acme")

    assert "numpy" not in denylist
    assert "pandas" in denylist


def test_walk_passes_a_package_that_imports_no_backend(isolated_modules: Path) -> None:
    _package(isolated_modules, "iso_clean_pkg", {"plain": "import json\n"})

    assert _check_no_backend_after_submodule_walk("iso_clean_pkg", frozenset({"iso_backend_a"})) == []


def test_walk_reports_a_backend_imported_at_module_scope(isolated_modules: Path) -> None:
    (isolated_modules / "iso_backend_b.py").write_text("")
    _package(isolated_modules, "iso_leaky_pkg", {"eager": "import iso_backend_b\n"})

    violations = _check_no_backend_after_submodule_walk("iso_leaky_pkg", frozenset({"iso_backend_b"}))

    assert len(violations) == 1
    assert "iso_backend_b" in violations[0]


def test_walk_allows_a_backend_imported_inside_a_method(isolated_modules: Path) -> None:
    (isolated_modules / "iso_backend_c.py").write_text("")
    _package(
        isolated_modules,
        "iso_lazy_pkg",
        {"lazy": "class Lazy:\n    @staticmethod\n    def run() -> None:\n        import iso_backend_c\n"},
    )

    assert _check_no_backend_after_submodule_walk("iso_lazy_pkg", frozenset({"iso_backend_c"})) == []


def test_walk_reports_a_submodule_that_cannot_import(isolated_modules: Path) -> None:
    _package(isolated_modules, "iso_broken_pkg", {"needs_extra": "import iso_missing_backend_zzz\n"})

    violations = _check_no_backend_after_submodule_walk("iso_broken_pkg", frozenset())

    assert len(violations) == 1
    assert "iso_broken_pkg.needs_extra" in violations[0]


def test_every_package_runs_the_submodule_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    walked: list[str] = []
    monkeypatch.setattr(check_install_isolation, "_check_closure", lambda _package: [])
    monkeypatch.setattr(check_install_isolation, "_check_imports", lambda _package: [])
    monkeypatch.setattr(check_install_isolation, "_backend_denylist_for", lambda _package: frozenset())
    monkeypatch.setattr(
        check_install_isolation,
        "_check_no_backend_after_submodule_walk",
        lambda import_name, _denylist: walked.append(import_name) or [],
    )
    for package in sorted(check_install_isolation._EXPECTED_PIRN_CLOSURE):
        monkeypatch.setattr(sys, "argv", ["check_install_isolation.py", "--package", package])
        assert check_install_isolation.main() == 0

    assert sorted(walked) == sorted(check_install_isolation._IMPORT_NAME.values())
