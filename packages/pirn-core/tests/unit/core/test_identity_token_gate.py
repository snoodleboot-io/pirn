"""Gate: no identity or canonical form is built from an object address (PIR-852).

``PirnOpaqueValue._pirn_identity_token`` is the single sanctioned per-instance
identity. An override of ``_pirn_audit_dict`` or ``__pirn_canonical__`` that
formats an address would bypass it, and a freed object's reused address would
repeat the token, which is a false match on replay. Six such overrides existed
before this gate (five in pirn-data, one in pirn-agents).

Inside those two hooks the scan flags:

* ``id`` used at all (called, or aliased as in ``ident = id``);
* ``builtins.id``, called or aliased;
* a module-level alias of either (``ident = id``, ``from builtins import id as
  ident``), when the alias is used in a hook;
* ``object.__repr__(...)``, whose default form embeds the address.

It does **not** follow calls into helper methods or functions. A hook that
delegates to ``self._token()`` which formats ``id(self)`` is not caught; review
covers that.

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


def _is_builtin_id(node: ast.AST) -> bool:
    """Whether ``node`` names the builtin ``id`` directly or as ``builtins.id``."""
    if isinstance(node, ast.Name) and node.id == "id":
        return True
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "id"
        and isinstance(node.value, ast.Name)
        and node.value.id == "builtins"
    )


def _module_level_id_aliases(tree: ast.Module) -> set[str]:
    """Names bound to the builtin ``id`` at module level."""
    aliases: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and _is_builtin_id(node.value):
            aliases.update(t.id for t in node.targets if isinstance(t, ast.Name))
        if isinstance(node, ast.ImportFrom) and node.module == "builtins":
            aliases.update(alias.asname or alias.name for alias in node.names if alias.name == "id")
    return aliases


def _is_object_repr_call(node: ast.AST) -> bool:
    """Whether ``node`` is a call of ``object.__repr__``."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "__repr__"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "object"
    )


def _address_uses_in_identity_hooks(source: Path) -> list[str]:
    """List ``file:line`` for each address-derived construct inside a hook override."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    aliases = _module_level_id_aliases(tree)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in {"_pirn_audit_dict", "__pirn_canonical__"}:
            continue
        for inner in ast.walk(node):
            flagged = (
                _is_builtin_id(inner)
                or (isinstance(inner, ast.Name) and inner.id in aliases)
                or _is_object_repr_call(inner)
            )
            if flagged:
                offenders.append(f"{source}:{getattr(inner, 'lineno', '?')} ({node.name})")
    return offenders


def _scan_snippet(tmp_path: Path, body: str) -> list[str]:
    """Write ``body`` as a module and scan it."""
    source = tmp_path / "offender.py"
    source.write_text(body, encoding="utf-8")
    return _address_uses_in_identity_hooks(source)


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
    offenders = [hit for path in sources for hit in _address_uses_in_identity_hooks(path)]

    # Assert
    assert sources, "the scan found no source files; the gate tested nothing"
    assert offenders == [], (
        "use PirnOpaqueValue._pirn_identity_token() instead of an address: " + ", ".join(offenders)
    )


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            "class W:\n    def _pirn_audit_dict(self):\n        return f'<W@{id(self._c):x}>'\n",
            id="id-call",
        ),
        pytest.param(
            "import builtins\n"
            "class W:\n    def __pirn_canonical__(self):\n        return builtins.id(self)\n",
            id="builtins-id-call",
        ),
        pytest.param(
            "class W:\n    def _pirn_audit_dict(self):\n        ident = id\n        return ident(self)\n",
            id="local-alias",
        ),
        pytest.param(
            "import builtins\nclass W:\n    def _pirn_audit_dict(self):\n"
            "        ident = builtins.id\n        return ident(self)\n",
            id="local-builtins-alias",
        ),
        pytest.param(
            "ident = id\nclass W:\n    def _pirn_audit_dict(self):\n        return ident(self)\n",
            id="module-alias",
        ),
        pytest.param(
            "from builtins import id as ident\n"
            "class W:\n    def __pirn_canonical__(self):\n        return ident(self)\n",
            id="import-alias",
        ),
        pytest.param(
            "class W:\n    def _pirn_audit_dict(self):\n        return object.__repr__(self)\n",
            id="object-repr",
        ),
    ],
)
def test_scanner_flags_address_derived_hook_bodies(tmp_path: Path, body: str) -> None:
    # Arrange / Act
    offenders = _scan_snippet(tmp_path, body)

    # Assert
    assert offenders, "the scanner missed an address-derived construct"


def test_scanner_accepts_the_hardened_token_and_ignores_id_outside_hooks(tmp_path: Path) -> None:
    # Arrange
    body = (
        "class W:\n"
        "    def key(self):\n"
        "        return id(self)\n"
        "    def _pirn_audit_dict(self):\n"
        "        return f'<W@{self._pirn_identity_token()}>'\n"
    )

    # Act
    offenders = _scan_snippet(tmp_path, body)

    # Assert
    assert offenders == []
