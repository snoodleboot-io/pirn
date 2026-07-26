"""Tests for the no-import-forwarding gate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_no_import_forwarding  # noqa: E402
from check_no_import_forwarding import check_file, main, resolve_paths  # noqa: E402


def _pkg(tmp_path: Path, name: str) -> Path:
    """Create ``tmp_path/<name>/<name>/`` as an importable-looking package root."""
    root = tmp_path / name / name
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("")
    return root


def test_flags_unused_re_export(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    (root / "widget.py").write_text("class Widget: ...\n")
    init = root / "__init__.py"
    init.write_text("from acme.widget import Widget\n")
    violations = check_file(init)
    assert len(violations) == 1
    assert "Widget" in violations[0]


def test_allows_a_used_import(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    (root / "probe.py").write_text("class Probe:\n    value = 1\n")
    init = root / "__init__.py"
    # Imported AND used — this is consumption, not forwarding.
    init.write_text("from acme.probe import Probe\n\nvalue = Probe.value\n")
    assert check_file(init) == []


def test_allows_third_party_import(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    init = root / "__init__.py"
    init.write_text("from collections.abc import Mapping\n")
    assert check_file(init) == []


def test_allows_future_import(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    init = root / "__init__.py"
    init.write_text("from __future__ import annotations\n")
    assert check_file(init) == []


def test_flags_star_re_export(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    (root / "widget.py").write_text("class Widget: ...\n")
    init = root / "__init__.py"
    init.write_text("from acme.widget import *\n")
    violations = check_file(init)
    assert len(violations) == 1
    assert "star re-export" in violations[0]


def test_re_export_in_all_is_still_forwarding(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    (root / "widget.py").write_text("class Widget: ...\n")
    init = root / "__init__.py"
    # Listing a forwarded name in __all__ does not make it "used".
    init.write_text('from acme.widget import Widget\n\n__all__ = ["Widget"]\n')
    assert len(check_file(init)) == 1


def test_ignores_non_init_files(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    mod = root / "widget.py"
    mod.write_text("from acme.other import Thing\n")
    assert check_file(mod) == []


def test_nested_subpackage_is_checked(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    sub = root / "sub"
    sub.mkdir()
    (sub / "widget.py").write_text("class Widget: ...\n")
    init = sub / "__init__.py"
    init.write_text("from acme.sub.widget import Widget\n")
    violations = check_file(init)
    assert len(violations) == 1
    assert "Widget" in violations[0]


def test_flags_forwarding_under_type_checking(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    (root / "widget.py").write_text("class Widget: ...\n")
    init = root / "__init__.py"
    init.write_text(
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n    from acme.widget import Widget\n"
    )
    violations = check_file(init)
    assert len(violations) == 1
    assert "Widget" in violations[0]


def test_allows_optional_dependency_fallback_in_try(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    (root / "fast.py").write_text("class Impl: ...\n")
    init = root / "__init__.py"
    # try/except ImportError is a legitimate optional-backend fallback, not a
    # public re-export, so it must not be flagged.
    init.write_text(
        "try:\n    from acme.fast import Impl\nexcept ImportError:\n    Impl = None\n"
    )
    assert check_file(init) == []


# --- CLI contract -----------------------------------------------------------
# A gate is only worth wiring into CI if a miswired invocation fails loudly. An
# earlier version dropped any argument not ending in ".py", so passing a
# directory scanned nothing and exited 0.


def _run(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["check_no_import_forwarding.py", *args])
    return main()


def test_resolve_paths_expands_a_directory(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    sub = root / "sub"
    sub.mkdir()
    (sub / "__init__.py").write_text("")
    files, errors = resolve_paths([str(tmp_path)])
    assert errors == []
    assert sorted(f.parent.name for f in files) == ["acme", "sub"]


def test_resolve_paths_skips_vendored_trees(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    vendored = root / ".venv" / "dep"
    vendored.mkdir(parents=True)
    (vendored / "__init__.py").write_text("")
    files, _ = resolve_paths([str(tmp_path)])
    assert all(".venv" not in f.parts for f in files)


def test_directory_argument_finds_violations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _pkg(tmp_path, "acme")
    (root / "widget.py").write_text("class Widget: ...\n")
    (root / "__init__.py").write_text("from acme.widget import Widget\n")
    # The regression this guards: a directory argument must actually be scanned.
    assert _run(monkeypatch, str(tmp_path)) == 1


def test_directory_with_no_inits_is_an_error_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "empty").mkdir()
    assert _run(monkeypatch, str(tmp_path / "empty")) == 2


def test_missing_path_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(monkeypatch, str(tmp_path / "nope")) == 2


def test_non_python_file_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("not python\n")
    assert _run(monkeypatch, str(readme)) == 2


def test_no_arguments_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(monkeypatch) == 2


def test_clean_tree_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _pkg(tmp_path, "acme")
    (root / "__init__.py").write_text('"""Docstring."""\n\n__all__: list[str] = []\n')
    assert _run(monkeypatch, str(tmp_path)) == 0


def test_file_arguments_still_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # pre-commit passes explicit file paths; that path must keep working.
    root = _pkg(tmp_path, "acme")
    (root / "widget.py").write_text("class Widget: ...\n")
    init = root / "__init__.py"
    init.write_text("from acme.widget import Widget\n")
    assert _run(monkeypatch, str(init)) == 1


def test_duplicate_paths_are_scanned_once(tmp_path: Path) -> None:
    root = _pkg(tmp_path, "acme")
    init = root / "__init__.py"
    files, _ = resolve_paths([str(tmp_path), str(init)])
    assert files.count(init) == 1


def test_allowlist_is_empty() -> None:
    # PIR-744 removed the only exemptions; refilling it needs a reviewed reason.
    assert check_no_import_forwarding._ALLOWLIST == frozenset()
