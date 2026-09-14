"""Tests for the pyright strict-list ratchet gate (PIR-869).

Only the pure pieces are tested here — subpackage naming, per-subpackage
counting of a pyright JSON report, pyproject parsing, and the policy rules.
Running pyright itself is exercised by the ``lint`` job in CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_pyright_strict_list as gate  # noqa: E402


def _package(tmp_path: Path, *, strict: list[str] | None = None) -> Path:
    """A ``packages/acme`` layout: ``acme/{__init__,root_mod}.py`` + ``acme/{alpha,beta}/``."""
    package_dir = tmp_path / "acme"
    root = package_dir / "acme"
    for sub in ("alpha", "beta"):
        (root / sub).mkdir(parents=True)
        (root / sub / "__init__.py").write_text("")
    (root / "__init__.py").write_text("")
    (root / "root_mod.py").write_text("")
    (root / "not_a_package").mkdir()
    strict_line = f"strict = {strict!r}\n" if strict is not None else ""
    (package_dir / "pyproject.toml").write_text(
        f'[tool.pyright]\ninclude = ["acme"]\n{strict_line}'
    )
    return package_dir


# --- subpackage naming -------------------------------------------------------


def test_enumerate_lists_init_dirs_and_root_glob(tmp_path: Path) -> None:
    package_dir = _package(tmp_path)
    assert gate._Subpackages.enumerate(package_dir, "acme") == [
        "acme/alpha",
        "acme/beta",
        "acme/*.py",
    ]


def test_key_for_maps_nested_file_to_top_level_subpackage(tmp_path: Path) -> None:
    package_dir = _package(tmp_path)
    nested = package_dir / "acme" / "alpha" / "deep" / "mod.py"
    assert gate._Subpackages.key_for(str(nested), package_dir, "acme") == "acme/alpha"


def test_key_for_maps_root_module_to_root_glob(tmp_path: Path) -> None:
    package_dir = _package(tmp_path)
    root_mod = package_dir / "acme" / "root_mod.py"
    assert gate._Subpackages.key_for(str(root_mod), package_dir, "acme") == "acme/*.py"


def test_key_for_ignores_files_outside_import_root(tmp_path: Path) -> None:
    package_dir = _package(tmp_path)
    assert gate._Subpackages.key_for(str(tmp_path / "elsewhere.py"), package_dir, "acme") is None


# --- counting ---------------------------------------------------------------


def test_count_only_errors_and_every_subpackage_present(tmp_path: Path) -> None:
    package_dir = _package(tmp_path)
    root = package_dir / "acme"
    diagnostics: list[dict[str, object]] = [
        {"file": str(root / "alpha" / "a.py"), "severity": "error"},
        {"file": str(root / "alpha" / "b.py"), "severity": "error"},
        {"file": str(root / "alpha" / "c.py"), "severity": "warning"},
        {"file": str(root / "root_mod.py"), "severity": "error"},
        {"file": str(tmp_path / "outside.py"), "severity": "error"},
    ]
    counts = gate._StrictRun.count(diagnostics, package_dir, "acme")
    assert counts == {"acme/alpha": 2, "acme/beta": 0, "acme/*.py": 1}


# --- pyproject parsing ------------------------------------------------------


def test_load_reads_include_and_strict(tmp_path: Path) -> None:
    package_dir = _package(tmp_path, strict=["acme/beta"])
    assert gate._PyrightConfig.load(package_dir) == ("acme", ["acme/beta"])


def test_load_defaults_strict_to_empty(tmp_path: Path) -> None:
    package_dir = _package(tmp_path)
    assert gate._PyrightConfig.load(package_dir) == ("acme", [])


def test_load_rejects_missing_include(tmp_path: Path) -> None:
    package_dir = tmp_path / "acme"
    package_dir.mkdir()
    (package_dir / "pyproject.toml").write_text("[tool.pyright]\nstrict = []\n")
    with pytest.raises(ValueError, match="include"):
        gate._PyrightConfig.load(package_dir)


# --- policy -----------------------------------------------------------------


def test_policy_holds_when_list_matches_zero_count_set() -> None:
    counts = {"acme/alpha": 3, "acme/beta": 0, "acme/*.py": 0}
    assert gate._Policy.problems(["acme/beta", "acme/*.py"], counts) == []


def test_policy_flags_regression_in_listed_subpackage() -> None:
    counts = {"acme/alpha": 3, "acme/beta": 1}
    problems = gate._Policy.problems(["acme/beta"], counts)
    assert problems == ["acme/beta is strict-listed but has 1 strict error(s) — regression"]


def test_policy_flags_zero_count_subpackage_missing_from_list() -> None:
    counts = {"acme/alpha": 0, "acme/beta": 2}
    problems = gate._Policy.problems([], counts)
    assert problems == ["acme/alpha has 0 strict errors but is not in the strict list — add it"]


def test_policy_flags_unknown_listed_path() -> None:
    problems = gate._Policy.problems(["acme/nope"], {"acme/alpha": 0})
    assert "strict list names 'acme/nope', which is not a subpackage" in problems


def test_table_rows_sorted_by_count_then_name() -> None:
    rows = gate._Policy.table_rows("acme", ["acme/beta"], {"acme/alpha": 2, "acme/beta": 0})
    assert rows == [
        "| acme | `acme/beta` | 0 | yes |",
        "| acme | `acme/alpha` | 2 |  |",
    ]


# --- CLI contract -----------------------------------------------------------


def test_no_arguments_is_a_usage_error() -> None:
    assert gate.main([]) == 2


def test_missing_pyproject_is_a_usage_error(tmp_path: Path) -> None:
    assert gate.main([str(tmp_path)]) == 2
