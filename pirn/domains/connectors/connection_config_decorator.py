"""``@connection_config`` decorator — safe-default replacement for ``@dataclass``.

Equivalent to ``@dataclass(frozen=True, repr=False)`` plus preservation of
the redacting ``__repr__`` defined on
:class:`pirn.domains.connectors.connection_config.ConnectionConfig`.

Use in place of ``@dataclass`` when declaring connector configs. Forgetting
``repr=False`` on a manual ``@dataclass`` would silently regenerate a
credential-leaking ``__repr__`` — this decorator removes that foot-gun.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, TypeVar, overload


_T = TypeVar("_T")


@overload
def connection_config(cls: type[_T], /) -> type[_T]: ...
@overload
def connection_config(
    *, frozen: bool = True, **dataclass_kwargs: Any
) -> Callable[[type[_T]], type[_T]]: ...


def connection_config(
    cls: type[_T] | None = None,
    /,
    *,
    frozen: bool = True,
    **dataclass_kwargs: Any,
) -> type[_T] | Callable[[type[_T]], type[_T]]:
    """Decorator wrapper around :func:`dataclasses.dataclass` with safe defaults.

    Always passes ``repr=False`` to dataclass so the inherited
    :meth:`ConnectionConfig.__repr__` survives. Strips any locally-generated
    ``__repr__`` defensively in case the underlying dataclass behaviour
    changes in a future Python version.
    """

    def wrap(target: type[_T]) -> type[_T]:
        decorated = dataclasses.dataclass(
            frozen=frozen, repr=False, **dataclass_kwargs
        )(target)
        if "__repr__" in decorated.__dict__:
            del decorated.__dict__["__repr__"]  # type: ignore[arg-type]
        return decorated

    if cls is None:
        return wrap
    return wrap(cls)
