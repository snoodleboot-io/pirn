"""Discover and import installed pirn domain packages.

Domains ship as standalone distributions (``pirn-signal``, ``pirn-data`` …)
whose import packages are ``pirn_signal``, ``pirn_data`` … Importing each one
triggers its ``Registry.fill_registry()`` self-registration, making its knots
resolvable by bare name through sweet_tea's factory. This module finds which
domain distributions are installed and imports the corresponding packages.
"""

from __future__ import annotations

import importlib
from importlib.metadata import distributions
from importlib.util import find_spec


class _DomainDiscovery:
    """Locate installed pirn domain import-packages and import them.

    The six domain names are fixed framework data, kept as an instance
    attribute rather than a module constant. ``pirn`` (core) is intentionally
    excluded — it self-registers on its own import.
    """

    def __init__(self) -> None:
        self._domains: tuple[str, ...] = (
            "agents",
            "data",
            "health",
            "ml",
            "oilgas",
            "signal",
        )

    def installed_import_names(self) -> tuple[str, ...]:
        """Return the ``pirn_<x>`` import names whose distribution is installed.

        Introspects installed distributions via
        :func:`importlib.metadata.distributions`, matching the canonical
        ``pirn-<domain>`` distribution names, then keeps only those whose
        import package is actually resolvable on ``sys.path``.
        """
        wanted = {f"pirn-{domain}": f"pirn_{domain}" for domain in self._domains}
        found: set[str] = set()
        for dist in distributions():
            dist_name = dist.metadata["Name"]
            if dist_name is None:
                continue
            normalized = dist_name.replace("_", "-").lower()
            import_name = wanted.get(normalized)
            if import_name is not None and find_spec(import_name) is not None:
                found.add(import_name)
        return tuple(sorted(found))

    def discover(self) -> tuple[str, ...]:
        """Import every installed domain package; return what was imported.

        Idempotent — re-importing an already-imported module is a no-op.
        Genuine import errors are not swallowed: they propagate wrapped in an
        :class:`ImportError` that names the offending package for context.
        """
        imported: list[str] = []
        for import_name in self.installed_import_names():
            try:
                importlib.import_module(import_name)
            except ImportError as exc:
                raise ImportError(
                    f"failed to import discovered pirn domain {import_name!r}: {exc}"
                ) from exc
            imported.append(import_name)
        return tuple(imported)


def discover_installed_domains() -> tuple[str, ...]:
    """Import all installed pirn domain packages and return their import names.

    Each imported ``pirn_<x>`` package self-registers its knots via
    ``Registry.fill_registry()``, so after this call their knots resolve by
    bare name through sweet_tea's factory (the same path the YAML loader
    uses). Returns the sorted tuple of import names that were imported. Safe
    to call repeatedly.
    """
    return _DomainDiscovery().discover()
