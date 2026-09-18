"""``ConstantThunk`` — adapts a pre-bound value into a zero-argument callable.

:meth:`~pirn_agents.builder.agent_references.AgentReferences.as_known_callables`
hands a caller-owned live object (an ``LLMProvider``, a ``MemoryStore``, a
``Tool``) to core's YAML loader as a ``known_callables`` entry. The loader's
``source`` node resolves its ``callable:`` reference and wraps it with
:meth:`pirn.core.knot_factory.KnotFactory.knot`, which expects an actual callable —
``KnotFactory.create`` reads ``fn.__name__``, ``fn.__qualname__`` and
``fn.__doc__`` directly (not via ``getattr`` with a default), so a bare
already-constructed object cannot stand in for the reference on its own.
This class is that adapter: call it with no arguments and it returns the
value it was built with, and it carries the function-shaped attributes
``KnotFactory.create`` reads.

It carries no ``__globals__``: ``KnotFactory`` gives the ``process`` it
generates for an unannotated callable annotations that are already type
objects, so nothing has to be resolved against the wrapped callable's module
(PIR-873).
"""

from __future__ import annotations

from typing import Any


class ConstantThunk:
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

    def __call__(self) -> Any:
        """Return the bound value."""
        return self._value
