"""Deprecation shim for the legacy ``pirn.domains.*`` import paths.

The six pirn domains now ship as standalone distributions —
``pirn_signal``, ``pirn_oilgas``, ``pirn_data``, ``pirn_ml``, ``pirn_agents``,
and ``pirn_health``. Legacy ``pirn.domains.<x>`` imports keep working: they
defer to the installed ``pirn_<x>`` package and emit a
:class:`DeprecationWarning`. Run the ``pirn-migrate-imports`` codemod to
rewrite call sites, or import ``pirn_<x>`` directly.

Two cooperating mechanisms back the shim:

- :class:`pirn.domains._domain_compat_finder.DomainCompatFinder` (registered
  on :data:`sys.meta_path`) handles ``import pirn.domains.<x>`` statements,
  which go through the import system rather than ``__getattr__``.
- :func:`__getattr__` below handles ``from pirn.domains import <x>`` and
  attribute access, delegating to the same finder so behaviour is identical.

Core never imports a domain at module level; resolution is fully deferred, so
core keeps zero hard dependency on any domain package.
"""

from __future__ import annotations

from types import ModuleType

from pirn.domains._domain_compat_finder import DomainCompatFinder

DomainCompatFinder.register()

__all__: list[str] = []


def __getattr__(name: str) -> ModuleType:
    """Resolve ``pirn.domains.<x>`` attribute access to ``pirn_<x>``.

    Delegates to :class:`DomainCompatFinder` for the six known domains
    (emitting the deprecation warning and the actionable ``ImportError`` when
    the backing package is absent). Any other name raises
    :class:`AttributeError`, so real missing-attribute errors are never
    shadowed.
    """
    if DomainCompatFinder.resolve_target(f"{DomainCompatFinder.legacy_prefix}{name}") is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return DomainCompatFinder.import_legacy(f"{DomainCompatFinder.legacy_prefix}{name}")
