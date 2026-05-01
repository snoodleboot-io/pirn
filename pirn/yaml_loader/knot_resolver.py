"""Resolves a string name to a registered :class:`Knot` subclass.

Used by the YAML loader to map ``callable: <name>`` entries onto the class
the loader will instantiate. Registration itself is handled by sweet_tea —
either through :meth:`sweet_tea.registry.Registry.fill_registry` (the
recommended way; auto-discovers every class in a package) or through a
direct :meth:`sweet_tea.registry.Registry.register` call.

Pirn's own classes are registered automatically when ``pirn`` is imported,
because ``pirn/__init__.py`` calls ``Registry.fill_registry()`` over the
pirn package tree. **Users who define their own** ``Knot`` **subclasses
must call** ``Registry.fill_registry()`` **from their own project's
package init** so those classes appear under the expected library name.

This resolver is the lookup side only — it never registers — which avoids
mixing the registration and query phases sweet_tea's caching expects to be
distinct.
"""

from __future__ import annotations

from sweet_tea.base_factory import BaseFactory
from sweet_tea.registry import Registry

from pirn.core.knot import Knot


class KnotResolver:
    """Looks up :class:`Knot` subclasses by name from sweet_tea's registry.

    The resolver applies the same key-variation handling as sweet_tea's
    :class:`AbstractFactory` (CamelCase, snake_case, no-underscores all
    resolve to the same entry), and it filters by ``lookup_type=Knot`` so
    only Knot subclasses are returned regardless of what else lives in the
    registry.

    Parameters
    ----------
    library:
        Optional library filter. When ``None`` (the default), entries from
        any library match. When set, only entries whose ``library`` equals
        this string match — useful for projects that want to restrict
        resolution to their own knots.
    """

    def __init__(self, library: str | None = None) -> None:
        self._library = library.lower() if library is not None else None

    @property
    def library(self) -> str | None:
        return self._library

    def has(self, name: str) -> bool:
        """Return True when a Knot subclass is registered under ``name``."""
        return self._find(name) is not None

    def get_class(self, name: str) -> type[Knot]:
        """Return the registered Knot subclass for ``name``.

        Raises ``KeyError`` if no entry matches.
        """
        result = self._find(name)
        if result is None:
            raise KeyError(f"no Knot registered under {name!r}")
        return result

    def _find(self, name: str) -> type[Knot] | None:
        variations = BaseFactory._generate_key_variations(name)
        entries = Registry.typed_entries(lookup_type=Knot)
        for variation in variations:
            for entry in entries:
                if entry.key != variation:
                    continue
                if self._library is not None and entry.library != self._library:
                    continue
                return entry.class_def
        return None
