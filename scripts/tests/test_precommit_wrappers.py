"""Tests for the pre-commit per-package wrappers (PIR-856).

Only the pure grouping/resolution logic is tested here — actually invoking
``ruff``/``pyright`` as subprocesses is exercised manually (see the module
docstrings) and by the real pre-commit hooks in CI, not unit-tested here.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gatekit.package_root_locator import PackageRootLocator
from precommit_pyright import PrecommitPyright
from precommit_ruff import PrecommitRuff


def test_package_root_finds_dist_directory() -> None:
    path = Path("/repo/packages/pirn-agents/pirn_agents/tool/toolset.py")
    assert PackageRootLocator.locate(path) == Path("/repo/packages/pirn-agents")


def test_package_root_none_outside_packages_tree() -> None:
    path = Path("/repo/scripts/check_conventions.py")
    assert PackageRootLocator.locate(path) is None


def test_group_by_package_splits_by_distribution() -> None:
    files = [
        "packages/pirn-core/pirn/backends/azure.py",
        "packages/pirn-signal/pirn_signal/__init__.py",
        "packages/pirn-core/tests/unit/test_x.py",
        "scripts/check_conventions.py",
    ]
    groups, unmatched = PrecommitRuff.group_by_package(files)
    assert unmatched == ["scripts/check_conventions.py"]
    core_root = Path("packages/pirn-core").resolve()
    signal_root = Path("packages/pirn-signal").resolve()
    assert set(groups) == {core_root, signal_root}
    assert len(groups[core_root]) == 2
    assert len(groups[signal_root]) == 1


def test_unique_package_roots_deduplicates() -> None:
    files = [
        "packages/pirn-core/pirn/backends/azure.py",
        "packages/pirn-core/pirn/backends/disk.py",
        "packages/pirn-signal/pirn_signal/__init__.py",
    ]
    roots, unmatched = PrecommitPyright.unique_package_roots(files)
    assert unmatched == []
    assert roots == [Path("packages/pirn-core").resolve(), Path("packages/pirn-signal").resolve()]


def test_unique_package_roots_reports_unmatched() -> None:
    roots, unmatched = PrecommitPyright.unique_package_roots(["scripts/check_conventions.py"])
    assert roots == []
    assert unmatched == ["scripts/check_conventions.py"]


def test_main_usage_error_without_mode() -> None:
    assert PrecommitRuff.main([]) == 2


def test_main_usage_error_with_bad_mode() -> None:
    assert PrecommitRuff.main(["lint", "file.py"]) == 2


def test_pyright_main_usage_error_without_files() -> None:
    assert PrecommitPyright.main([]) == 2
