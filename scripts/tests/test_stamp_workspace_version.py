"""Tests for the lockstep version stamper/gate (PIR-873 class conversion)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stamp_agentic_use_version import StampAgenticUseVersion
from stamp_workspace_version import StampWorkspaceVersion

_repo_root = Path(__file__).resolve().parents[2]


def test_upper_bound_is_next_minor_while_zero_major() -> None:
    assert StampWorkspaceVersion._upper_bound("0.9.0") == "0.10.0"


def test_upper_bound_is_next_major_from_one_onward() -> None:
    assert StampWorkspaceVersion._upper_bound("1.2.3") == "2.0.0"


def test_upper_bound_rejects_a_non_semver_version() -> None:
    with pytest.raises(ValueError, match=r"MAJOR\.MINOR\.PATCH"):
        StampWorkspaceVersion._upper_bound("nightly")


def test_stamp_text_rewrites_the_version_and_every_pin() -> None:
    text = (
        '[project]\nname = "pirn-ml"\nversion = "0.9.0"\n'
        'dependencies = ["pirn-core>=0.9.0,<0.10.0", "pirn-data>=0.9.0,<0.10.0"]\n'
    )
    updated = StampWorkspaceVersion._stamp_text(text, "0.10.0", "0.11.0")
    assert 'version = "0.10.0"' in updated
    assert updated.count(">=0.10.0,<0.11.0") == 2


def test_stamp_text_leaves_a_third_party_pin_alone() -> None:
    text = '[project]\nversion = "0.9.0"\ndependencies = ["numpy>=0.9.0,<0.10.0"]\n'
    assert "numpy>=0.9.0,<0.10.0" in StampWorkspaceVersion._stamp_text(text, "0.10.0", "0.11.0")


def test_real_repository_is_lockstep_consistent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_repo_root)
    assert StampWorkspaceVersion.check(None) == []


def test_agentic_use_major_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAJOR_VERSION", "7")
    assert StampAgenticUseVersion._major_from_env() == 7


def test_agentic_use_major_ignores_a_non_numeric_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAJOR_VERSION", "v7")
    assert StampAgenticUseVersion._major_from_env() is None


def test_agentic_use_major_falls_back_to_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "3.1.4"\n')
    assert StampAgenticUseVersion._major_from_pyproject(tmp_path) == 3


def test_agentic_use_major_is_zero_without_a_pyproject(tmp_path: Path) -> None:
    assert StampAgenticUseVersion._major_from_pyproject(tmp_path) == 0
