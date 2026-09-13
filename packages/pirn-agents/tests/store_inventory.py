"""``StoreInventory`` — find every keyed store and every RunState/RunCheckpoint/
Cassette* importer in ``pirn_agents``.

Shared by ``test_store_inventory_ratchet.py`` (the frozen ratchet asserted by
exact equality). ADR "agents speaks core" WS3 burns this inventory down as
memory/sessions/determinism move onto core's ``DataStore``/``RunHistory``
value and lineage planes (PIR-856); until then this freezes what exists so a
*new* keyed store, or a *new* module reaching into the session/determinism
value shapes being replaced, fails loudly here instead of silently growing
the surface WS3 is meant to shrink.

Two independent walks:

* :meth:`discover_store_classes` — every class defined in ``pirn_agents``
  whose method surface (own or inherited) exposes a keyed-store shape:
  ``store``/``retrieve``/``forget``, ``put``/``get``, ``save``/``load``, or
  ``search`` alongside any of those (search "over a namespace" — a bare
  similarity search with no keyed accessor next to it is not a *store*).
  This is a runtime scan (``dir(cls)``) so a class that inherits its store
  contract from a base still counts — the same reasoning
  ``BypassInventory`` uses ``issubclass`` for: a renamed or inherited method
  cannot silently drop a class out of scope.
* :meth:`discover_lifecycle_importers` — every module that imports
  ``RunState``, ``RunCheckpoint``, or a ``*Cassette*`` name (by import or by
  importing from a module whose path contains ``cassette``). This is an AST
  scan over source text, not a runtime import, so it also sees modules an
  optional dependency would otherwise make expensive or conditional to
  import.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path
from typing import ClassVar

import pirn_agents


class StoreInventory:
    """Discovers keyed-store classes and RunState/RunCheckpoint/Cassette* importers."""

    #: Method-name pairs that, both present on a class's method resolution
    #: order, mark it as a keyed store.
    _STORE_METHOD_PAIRS: ClassVar[tuple[frozenset[str], ...]] = (
        frozenset({"store", "retrieve"}),
        frozenset({"put", "get"}),
        frozenset({"save", "load"}),
    )

    #: Any accessor that, alongside ``search``, marks the search as scoped to
    #: a keyed namespace rather than a bare similarity index.
    _NAMESPACE_ACCESSORS: ClassVar[frozenset[str]] = frozenset(
        {"store", "retrieve", "forget", "put", "get", "save", "load"}
    )

    #: Bare names whose import marks a module as a session/determinism
    #: lifecycle-value importer.
    _LIFECYCLE_NAMES: ClassVar[frozenset[str]] = frozenset({"RunState", "RunCheckpoint"})

    @staticmethod
    def discover_store_classes() -> dict[str, type]:
        """Return ``{"relative/path.py::ClassName": cls}`` for every keyed-store class.

        Membership is a runtime method-surface check (``dir(cls)``), so a
        concrete class that inherits its accessors unchanged from a base
        still counts.
        """
        root = Path(pirn_agents.__path__[0])
        found: dict[str, type] = {}
        for info in pkgutil.walk_packages(pirn_agents.__path__, pirn_agents.__name__ + "."):
            module = importlib.import_module(info.name)
            module_file = getattr(module, "__file__", None)
            if module_file is None:
                continue
            rel = Path(module_file).relative_to(root)
            for name in dir(module):
                obj = getattr(module, name, None)
                if not isinstance(obj, type) or obj.__module__ != info.name:
                    continue
                if StoreInventory.is_keyed_store(obj):
                    found[f"{rel}::{obj.__qualname__}"] = obj
        return dict(sorted(found.items()))

    @staticmethod
    def is_keyed_store(cls: type) -> bool:
        """True if ``cls``'s method surface exposes a keyed-store shape."""
        surface = StoreInventory._method_surface(cls)
        has_pair = any(pair <= surface for pair in StoreInventory._STORE_METHOD_PAIRS)
        has_namespaced_search = "search" in surface and bool(
            surface & StoreInventory._NAMESPACE_ACCESSORS
        )
        return has_pair or has_namespaced_search

    @staticmethod
    def _method_surface(cls: type) -> frozenset[str]:
        """Return the callable, non-dunder attribute names on ``cls``'s MRO."""
        return frozenset(
            name
            for name in dir(cls)
            if not name.startswith("_") and callable(getattr(cls, name, None))
        )

    @staticmethod
    def discover_lifecycle_importers() -> dict[str, tuple[str, ...]]:
        """Return ``{"relative/path.py": (matched_name, ...)}`` for every importer.

        A module matches when it imports ``RunState``/``RunCheckpoint`` by
        name, or imports any name containing ``Cassette``, or imports from a
        module whose dotted path contains ``cassette``. The file that defines
        the value itself (``run_state.py``, ``run_checkpoint.py``, and the
        ``determinism/*cassette*.py`` modules) is excluded — a definition is
        not an import of it.
        """
        root = Path(pirn_agents.__path__[0])
        found: dict[str, tuple[str, ...]] = {}
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(root)
            if "cassette" in path.stem.lower() or path.stem in {"run_state", "run_checkpoint"}:
                continue
            matched = StoreInventory._lifecycle_imports(path.read_text())
            if matched:
                found[str(rel)] = matched
        return found

    @staticmethod
    def _lifecycle_imports(source: str) -> tuple[str, ...]:
        """Return the sorted matched names imported by ``source``, if any."""
        tree = ast.parse(source)
        matched: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "cassette" in alias.name.lower():
                        matched.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                for alias in node.names:
                    candidate = alias.name
                    if (
                        candidate in StoreInventory._LIFECYCLE_NAMES
                        or "cassette" in candidate.lower()
                        or "cassette" in module_name.lower()
                    ):
                        matched.add(candidate)
        return tuple(sorted(matched))
