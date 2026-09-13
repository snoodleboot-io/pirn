"""Tests for the no-UPPER_SNAKE-constants gate, including the PIR-856 baseline ratchet."""

from __future__ import annotations

import json
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


def test_precommit_mode_fails_without_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = tmp_path / "mod.py"
    f.write_text("MY_CONST = 42\n")
    assert _run(monkeypatch, str(f)) == 1


def test_precommit_mode_passes_on_clean_file(
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


def test_package_of_extracts_dist_segment(tmp_path: Path) -> None:
    path = tmp_path / "packages" / "pirn-agents" / "pirn_agents" / "mod.py"
    assert check_no_caps_constants._package_of(path) == "pirn-agents"


def test_package_of_returns_empty_outside_packages_tree(tmp_path: Path) -> None:
    path = tmp_path / "scratch" / "mod.py"
    assert check_no_caps_constants._package_of(path) == ""


def test_write_baseline_then_clean_run_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = tmp_path / "packages" / "acme" / "acme"
    pkg.mkdir(parents=True)
    (pkg / "leak.py").write_text("LEAKED = 1\n")
    baseline = tmp_path / "baseline.json"

    assert _run(monkeypatch, str(pkg), "--baseline", str(baseline), "--write-baseline") == 0
    data = json.loads(baseline.read_text())
    assert data["acme"] == 1

    assert _run(monkeypatch, str(pkg), "--baseline", str(baseline)) == 0


def test_baseline_mode_fails_when_count_exceeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    pkg = tmp_path / "packages" / "acme" / "acme"
    pkg.mkdir(parents=True)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"acme": 0}))

    (pkg / "leak.py").write_text("LEAKED = 1\n")
    exit_code = _run(monkeypatch, str(pkg), "--baseline", str(baseline))
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "exceeds baseline" in out


def test_baseline_mode_notes_when_count_is_lower(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    pkg = tmp_path / "packages" / "acme" / "acme"
    pkg.mkdir(parents=True)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"acme": 5}))
    (pkg / "clean.py").write_text("clean = 1\n")

    exit_code = _run(monkeypatch, str(pkg), "--baseline", str(baseline))
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "baseline can be lowered" in out
