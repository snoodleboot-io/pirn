"""Gate: no identity or canonical form is built from ``id()`` (PIR-852).

``PirnOpaqueValue._pirn_identity_token`` is the single sanctioned per-instance
identity. An override of ``_pirn_audit_dict`` or ``__pirn_canonical__`` that
formats ``id(...)`` instead would bypass it, and a freed object's reused address
would repeat the token, which is a false match on replay. Six such overrides
existed before this gate (five in pirn-data, one in pirn-agents).

The scan covers the whole workspace, not just pirn-core, because the classes
that override these hooks live in every package.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _workspace_root() -> Path | None:
    """Return the monorepo root (the directory holding ``packages/``), if present."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "packages" / "pirn-core").is_dir():
            return parent
    return None


def _id_calls_in_identity_hooks(source: Path) -> list[str]:
    """List ``file:line`` for each ``id(...)`` call inside a hook override."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in {"_pirn_audit_dict", "__pirn_canonical__"}:
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == "id"
            ):
                offenders.append(f"{source}:{inner.lineno} ({node.name})")
    return offenders


def test_no_identity_hook_override_formats_an_object_address() -> None:
    # Arrange
    root = _workspace_root()
    if root is None:
        pytest.skip("not running inside the pirn monorepo checkout")
    sources = [
        path
        for folder in (root / "packages", root / "examples")
        if folder.is_dir()
        for path in folder.rglob("*.py")
        if ".venv" not in path.parts and "tests" not in path.parts
    ]

    # Act
    offenders = [hit for path in sources for hit in _id_calls_in_identity_hooks(path)]

    # Assert
    assert sources, "the scan found no source files; the gate tested nothing"
    assert offenders == [], (
        "use PirnOpaqueValue._pirn_identity_token() instead of id(): " + ", ".join(offenders)
    )


def test_scanner_flags_an_address_based_audit_override(tmp_path: Path) -> None:
    # Arrange — prove the gate has teeth on the exact pattern it replaced.
    source = tmp_path / "offender.py"
    source.write_text(
        "class Wrapper:\n"
        "    def _pirn_audit_dict(self):\n"
        "        return f'<Wrapper@{id(self._client):x}>'\n",
        encoding="utf-8",
    )

    # Act
    offenders = _id_calls_in_identity_hooks(source)

    # Assert
    assert len(offenders) == 1
