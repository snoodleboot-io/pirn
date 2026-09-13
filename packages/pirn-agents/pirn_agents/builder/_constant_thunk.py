"""``_ConstantThunk`` — adapts a pre-bound value into a zero-argument callable.

:meth:`~pirn_agents.builder.agent_references.AgentReferences.as_known_callables`
hands a caller-owned live object (an ``LLMProvider``, a ``MemoryStore``, a
``Tool``) to core's YAML loader as a ``known_callables`` entry. The loader's
``source`` node resolves its ``callable:`` reference and wraps it with
:func:`pirn.core.knot_factory.knot`, which expects an actual callable —
``KnotFactory.create`` reads ``fn.__name__``, ``fn.__qualname__`` and
``fn.__doc__`` directly (not via ``getattr`` with a default), so a bare
already-constructed object cannot stand in for the reference on its own.
This class is that adapter: call it with no arguments and it returns the
value it was built with, and it carries the function-shaped attributes
``KnotFactory.create`` reads.

It also carries ``__globals__``. ``KnotFactory``'s generated ``process``
method is ``@functools.wraps(fn)``-decorated, which sets
``process.__wrapped__ = fn``; ``Knot.__init_subclass__`` then calls
``typing.get_type_hints(process)`` to find ``Knot | T`` scalar-coercion
candidates, and ``get_type_hints`` resolves a wrapped callable's forward
-referenced annotations (``knot_factory.py`` has ``from __future__ import
annotations``, so ``**kwargs: Any -> Any`` are strings at that point) by
walking to the *end* of the ``__wrapped__`` chain and reading *that* object's
``__globals__`` — not ``knot_factory.py``'s own. A real function has one; a
plain callable instance like this one does not, so without this, ``Any``
comes back unresolvable and ``Knot`` disables coercion and I/O validation
for the generated knot, with a ``UserWarning`` at every construction.
"""

from __future__ import annotations

from typing import Any


class _ConstantThunk:
    """A zero-argument callable that always returns one fixed value."""

    def __init__(self, value: Any, *, label: str) -> None:
        """Bind ``value`` behind a callable named after its reference ``label``.

        Args:
            value: The live object to return on every call.
            label: The reference label this thunk stands in for — used as the
                generated callable's ``__name__``/``__qualname__`` so the
                dynamically-built knot class core's loader creates is named
                after the reference, not after this adapter.
        """
        self._value = value
        self.__name__ = label
        self.__qualname__ = label
        self.__doc__ = f"Return the object registered under reference label {label!r}."
        # See the class docstring: `get_type_hints` needs *some* mapping
        # here to resolve `Any` in KnotFactory's generated `process` method.
        self.__globals__: dict[str, Any] = {"Any": Any}

    def __call__(self) -> Any:
        """Return the bound value."""
        return self._value
