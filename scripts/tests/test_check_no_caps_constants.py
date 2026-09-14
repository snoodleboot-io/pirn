"""Tests for the no-UPPER_SNAKE-constants gate (PIR-856): any finding fails."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_no_caps_constants  # noqa: E402
from check_no_caps_constants import check_file, main  # noqa: E402


def test_flags_module_level_constant(tmp_path: Path) -> None:
    f = tmp_path / "mod.py"
    f.write_text("MY_CONST = 42\n")
    violations = check_file(f)
    assert len(violations) == 1
    assert "MY_CONST" in violations[0]


def test_allows_enum_members(tmp_path: Path) -> None:
    f = tmp_path / "mod.py"
    f.write_text("from enum import Enum\n\n\nclass Color(Enum):\n    RED = 1\n")
    assert check_file(f) == []


def _run(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["check_no_caps_constants.py", *args])
    return main()


def test_file_argument_with_a_constant_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = tmp_path / "mod.py"
    f.write_text("MY_CONST = 42\n")
    assert _run(monkeypatch, str(f)) == 1


def test_file_argument_without_a_constant_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = tmp_path / "mod.py"
    f.write_text("my_value = 42\n")
    assert _run(monkeypatch, str(f)) == 0


def test_directory_argument_is_walked_skipping_tests_and_conftest(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "acme" / "acme"
    pkg.mkdir(parents=True)
    (pkg / "real.py").write_text("REAL_CONST = 1\n")
    tests_dir = pkg / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_real.py").write_text("TEST_CONST = 1\n")
    (pkg / "conftest.py").write_text("CONFTEST_CONST = 1\n")

    files = check_no_caps_constants._resolve_paths([str(pkg)])
    assert files == [pkg / "real.py"]


def test_directory_argument_with_one_constant_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pkg = tmp_path / "packages" / "acme" / "acme"
    pkg.mkdir(parents=True)
    (pkg / "leak.py").write_text("LEAKED = 1\n")

    exit_code = _run(monkeypatch, str(pkg))

    assert exit_code == 1
    assert "LEAKED" in capsys.readouterr().out


def test_clean_directory_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = tmp_path / "packages" / "acme" / "acme"
    pkg.mkdir(parents=True)
    (pkg / "clean.py").write_text("clean = 1\n")

    assert _run(monkeypatch, str(pkg)) == 0


def test_baseline_option_no_longer_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{}")

    with pytest.raises(SystemExit) as excinfo:
        _run(monkeypatch, str(tmp_path), "--baseline", str(baseline))

    assert excinfo.value.code == 2
