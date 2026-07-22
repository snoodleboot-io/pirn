"""Tests for the no-import-forwarding gate."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_no_import_forwarding import check_file  # noqa: E402


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
