"""Tests for the no-UPPER_SNAKE-constants gate (PIR-856/PIR-873): any finding fails."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_no_caps_constants import CheckNoCapsConstants


def _run(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["check_no_caps_constants.py", *args])
    return CheckNoCapsConstants.main()


def test_flags_module_level_constant(tmp_path: Path) -> None:
    f = tmp_path / "mod.py"
    f.write_text("MY_CONST = 42\n")
    violations = CheckNoCapsConstants.check_file(f)
    assert len(violations) == 1
    assert "MY_CONST" in violations[0]


def test_allows_enum_members(tmp_path: Path) -> None:
    f = tmp_path / "mod.py"
    f.write_text("from enum import Enum\n\n\nclass Color(Enum):\n    RED = 1\n")
    assert CheckNoCapsConstants.check_file(f) == []


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

    files, errors = CheckNoCapsConstants.resolve_paths([str(pkg)])
    assert errors == []
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


# --- PIR-873 (a): module scope is not just ``tree.body`` ---------------------
# The old gate walked only the top-level statement list, so any compound block
# at module scope hid a constant from it entirely.


def test_flags_constant_under_if_type_checking(tmp_path: Path) -> None:
    f = tmp_path / "mod.py"
    f.write_text("from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    HIDDEN_CONST = 1\n")
    violations = CheckNoCapsConstants.check_file(f)
    assert len(violations) == 1
    assert "HIDDEN_CONST" in violations[0]


def test_flags_constant_in_a_try_block(tmp_path: Path) -> None:
    f = tmp_path / "mod.py"
    f.write_text("try:\n    TRY_CONST = 1\nexcept ImportError:\n    EXCEPT_CONST = 2\n")
    violations = CheckNoCapsConstants.check_file(f)
    assert {"TRY_CONST", "EXCEPT_CONST"} == {
        name for name in ("TRY_CONST", "EXCEPT_CONST") if any(name in v for v in violations)
    }
    assert len(violations) == 2


def test_flags_constant_in_for_while_with_and_match_blocks(tmp_path: Path) -> None:
    f = tmp_path / "mod.py"
    f.write_text(
        "import contextlib\n\n"
        "for _item in ():\n    FOR_CONST = 1\n"
        "while False:\n    WHILE_CONST = 2\n"
        "with contextlib.suppress(Exception):\n    WITH_CONST = 3\n"
        "match 1:\n    case 1:\n        MATCH_CONST = 4\n"
    )
    violations = CheckNoCapsConstants.check_file(f)
    assert len(violations) == 4


def test_flags_class_level_constant_inside_a_compound_block(tmp_path: Path) -> None:
    f = tmp_path / "mod.py"
    f.write_text(
        "from typing import TYPE_CHECKING\n\n"
        "class Widget:\n"
        "    if TYPE_CHECKING:\n"
        "        NESTED_CONST = 1\n"
    )
    violations = CheckNoCapsConstants.check_file(f)
    assert len(violations) == 1
    assert "class-level constant 'NESTED_CONST'" in violations[0]


def test_enum_members_in_a_compound_block_are_still_allowed(tmp_path: Path) -> None:
    f = tmp_path / "mod.py"
    f.write_text("from enum import Enum\n\nclass Color(Enum):\n    if True:\n        RED = 1\n")
    assert CheckNoCapsConstants.check_file(f) == []


# --- PIR-873 (b): a file the gate cannot parse must fail, not pass -----------


def test_unparseable_file_is_a_violation(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def oops(:\n")
    violations = CheckNoCapsConstants.check_file(f)
    assert len(violations) == 1
    assert "could not parse" in violations[0]
    assert str(f) in violations[0]


def test_unparseable_file_fails_the_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "broken.py"
    f.write_text("class Oops(\n")
    assert _run(monkeypatch, str(f)) == 1


# --- PIR-873 (c): "checked nothing" must never exit 0 ------------------------


def test_missing_path_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(monkeypatch, str(tmp_path / "does-not-exist")) == 2


def test_directory_matching_no_python_files_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _run(monkeypatch, str(empty)) == 2


def test_directory_of_only_skipped_files_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = tmp_path / "acme"
    tests_dir = pkg / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_x.py").write_text("X_CONST = 1\n")
    assert _run(monkeypatch, str(pkg)) == 2


def test_no_arguments_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(monkeypatch) == 2


def test_only_non_python_file_arguments_exit_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # pre-commit hands hooks whatever it staged; a .md path is legitimately
    # nothing for this gate to check, unlike a path that does not exist.
    readme = tmp_path / "README.md"
    readme.write_text("not python\n")
    assert _run(monkeypatch, str(readme)) == 0


def test_a_missing_path_beats_a_usable_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    good = tmp_path / "mod.py"
    good.write_text("value = 1\n")
    assert _run(monkeypatch, str(good), str(tmp_path / "nope.py")) == 2
