"""``VocabularyInventory`` — static discovery for the WS2 core-vocabulary ratchet.

Mirrors ``tests.specializations.base.bypass_inventory.BypassInventory``: pure
``ast`` parsing over the package source tree, no runtime import of
``pirn_agents`` modules (which would pull in optional heavy dependencies for
no reason a static walk needs them). See
``tests/test_core_vocabulary_ratchet.py`` for what each discovery method
feeds.

The exception-root and outcome-enum detectors both need to know what a
class *ultimately* derives from without executing any code. They lean on two
invariants the codebase already enforces (``.claude/conventions/core/general.md``
"Class Organization Rules" and the registry-uniqueness rule in the ADR
brief): one class per file, and class names unique across the whole
workspace. That means a base-class name that is not itself defined
somewhere in the ``pirn_agents`` source tree is either a builtin
(``Exception``, ``ValueError``, …), a core type (``PirnError``, ``Enum``,
…), or a third-party type — in every case, a name this walk cannot expand
further, so it is recorded as-is and treated as a leaf.
"""

from __future__ import annotations

import ast
from pathlib import Path


class VocabularyInventory:
    """Static discovery of class hierarchies under ``pirn_agents/``."""

    @staticmethod
    def iter_py_files(root: Path) -> list[Path]:
        return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)

    @staticmethod
    def discover_classes(root: Path) -> dict[str, tuple[str, list[str]]]:
        """Return ``{class_name: (relative_path, [base_name, ...])}`` for every class in ``root``.

        ``base_name`` is the base expression's source text with any
        subscript (``Generic[T]``) and module prefix (``abc.ABC``) stripped
        to its simple last component, so ``Ok[T]`` and ``ok.Ok`` both record
        as ``"Ok"``. Relies on the one-class-per-file / globally-unique-name
        conventions: a class name collision across files would silently keep
        only the last one seen, which the registry-uniqueness gate elsewhere
        in the pipeline is what actually prevents.
        """
        classes: dict[str, tuple[str, list[str]]] = {}
        for path in VocabularyInventory.iter_py_files(root):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            rel = path.relative_to(root).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases = [VocabularyInventory._simple_name(base) for base in node.bases]
                    classes[node.name] = (rel, bases)
        return classes

    @staticmethod
    def _simple_name(base: ast.expr) -> str:
        """Return the unparsed base expression's simple trailing name."""
        text = ast.unparse(base)
        return text.split("[", 1)[0].split(".")[-1]

    @staticmethod
    def all_reachable_bases(
        name: str, classes_by_name: dict[str, tuple[str, list[str]]]
    ) -> set[str]:
        """Return every base name reachable by walking up ``name``'s hierarchy.

        Includes both names resolvable within ``classes_by_name`` (walked
        further) and unresolvable leaves (builtins, core types, third-party
        bases) — the leaf itself is included, just not expanded past.
        """
        return VocabularyInventory._walk(name, classes_by_name, set())

    @staticmethod
    def _walk(
        name: str, classes_by_name: dict[str, tuple[str, list[str]]], seen: set[str]
    ) -> set[str]:
        entry = classes_by_name.get(name)
        if entry is None:
            return set()
        _, bases = entry
        reachable: set[str] = set()
        for base in bases:
            if base in seen:
                continue
            seen.add(base)
            reachable.add(base)
            reachable |= VocabularyInventory._walk(base, classes_by_name, seen)
        return reachable

    #: Builtin exception base names that mark a class as exception-shaped.
    BUILTIN_EXCEPTION_BASES = frozenset(
        {
            "BaseException",
            "Exception",
            "ValueError",
            "TypeError",
            "RuntimeError",
            "LookupError",
            "KeyError",
            "IndexError",
            "OSError",
            "IOError",
            "ArithmeticError",
            "AttributeError",
            "NotImplementedError",
            "StopIteration",
            "ImportError",
            "NameError",
            "AssertionError",
        }
    )

    @staticmethod
    def is_exception_class(name: str, classes_by_name: dict[str, tuple[str, list[str]]]) -> bool:
        """Return whether ``name`` ultimately derives from a builtin exception."""
        reachable = VocabularyInventory.all_reachable_bases(name, classes_by_name)
        return bool(reachable & VocabularyInventory.BUILTIN_EXCEPTION_BASES)

    @staticmethod
    def roots_on_pirn_error(name: str, classes_by_name: dict[str, tuple[str, list[str]]]) -> bool:
        """Return whether ``PirnError`` is anywhere in ``name``'s reachable bases."""
        return "PirnError" in VocabularyInventory.all_reachable_bases(name, classes_by_name)

    @staticmethod
    def imports_canonical_json(path: Path) -> bool:
        """Return whether the module at ``path`` imports ``CanonicalJson``."""
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                if any(alias.name == "CanonicalJson" for alias in node.names):
                    return True
            if isinstance(node, ast.Import):
                if any(alias.name.endswith("canonical_json") for alias in node.names):
                    return True
        return False

    @staticmethod
    def is_enum_class(name: str, classes_by_name: dict[str, tuple[str, list[str]]]) -> bool:
        """Return whether ``name`` derives from :class:`enum.Enum` (any mixin form)."""
        entry = classes_by_name.get(name)
        if entry is None:
            return False
        _, bases = entry
        if "Enum" in bases:
            return True
        return any(
            VocabularyInventory.is_enum_class(base, classes_by_name)
            for base in bases
            if base in classes_by_name
        )
