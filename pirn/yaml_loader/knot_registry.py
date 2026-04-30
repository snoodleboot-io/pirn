"""Global Knot registry backed by sweet_tea.

Users pre-register @knot factories or Knot subclasses by name so that
YAML pipelines can reference them without passing ``known_callables``
at every ``load_pipeline`` call::

    from pirn.yaml_loader.knot_registry import KnotRegistry
    from pirn.core.knot_factory import knot

    @knot
    async def double(x: int) -> int:
        return x * 2

    KnotRegistry.register("double", double)

The YAML loader checks the registry before falling back to dotted-path
imports, so ``known_callables`` remains supported as a higher-priority
per-call override for backward compatibility.
"""

from __future__ import annotations

from typing import Any

from sweet_tea.registry import Registry

from pirn.core.knot import Knot


class KnotRegistry:
    """Thin typed wrapper around sweet_tea Registry for Knot classes."""

    _LIBRARY = "pirn.knots"

    @classmethod
    def register(cls, name: str, factory_or_class: Any) -> None:
        """Register a ``@knot`` factory or ``Knot`` subclass under ``name``.

        Parameters
        ----------
        name:
            The string key used in YAML ``callable:`` fields.
        factory_or_class:
            A ``KnotFactory`` (returned by ``@knot``) or a ``Knot`` subclass.
        """
        from pirn.core.knot_factory import KnotFactory

        if isinstance(factory_or_class, KnotFactory):
            knot_class = factory_or_class.knot_class
        elif isinstance(factory_or_class, type) and issubclass(factory_or_class, Knot):
            knot_class = factory_or_class
        else:
            raise TypeError(
                f"KnotRegistry.register: expected a @knot KnotFactory or Knot subclass, "
                f"got {type(factory_or_class).__name__}"
            )
        Registry.register(name, knot_class, library=cls._LIBRARY)

    @classmethod
    def has(cls, name: str) -> bool:
        """Return True if ``name`` is registered as a Knot."""
        return any(
            e.key == name.lower()
            for e in Registry.typed_entries(lookup_type=Knot)
            if e.library == cls._LIBRARY
        )

    @classmethod
    def get_class(cls, name: str) -> type[Knot]:
        """Return the registered Knot subclass for ``name``.

        Raises ``KeyError`` if not found.
        """
        for e in Registry.typed_entries(lookup_type=Knot):
            if e.key == name.lower() and e.library == cls._LIBRARY:
                return e.class_def
        raise KeyError(f"KnotRegistry: no knot registered under {name!r}")

