"""KnotFactory and the ``knot`` decorator.

These live in a separate module from ``Knot`` to keep the core class
lightweight and to allow decorating functions without importing all of
``knot.py``'s runtime machinery.
"""

from __future__ import annotations

import asyncio
import functools

from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot


class KnotFactory:
    """Callable that constructs a ``Knot`` instance per invocation.

    Returned by ``@knot``.  Calling a factory ``f(**kwargs)`` constructs
    one of the underlying knot class.  Exposes the original function as
    ``.fn`` and the generated Knot subclass as ``.knot_class`` for
    introspection (used by the YAML loader, ``Map``'s ``each=`` handling,
    etc.).

    A real class — not a function with attached attributes — so callers
    can ``isinstance(obj, KnotFactory)`` instead of probing for a magic
    attribute.
    """

    def __init__(self, fn: Callable[..., Any], knot_class: type[Knot]) -> None:
        self.fn = fn
        self.knot_class = knot_class
        # Mirror common function-object metadata so introspection tools
        # (help(), Sphinx autodoc, etc.) see the original function's name
        # and docstring on the factory.
        self.__name__ = fn.__name__
        self.__doc__ = fn.__doc__
        self.__wrapped__ = fn

    def __call__(self, **kwargs: Any) -> Knot:
        return self.knot_class(**kwargs)

    def __repr__(self) -> str:
        return f"<KnotFactory for {self.fn.__qualname__}>"


def _make_async_process(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    async def process(self, **kwargs: Any) -> Any:
        return await fn(**kwargs)

    return process


def _make_sync_process(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    async def process(self, **kwargs: Any) -> Any:
        return await asyncio.to_thread(fn, **kwargs)

    return process


def _make_knot_factory(fn: Callable[..., Any]) -> KnotFactory:
    process = _make_async_process(fn) if asyncio.iscoroutinefunction(fn) else _make_sync_process(fn)
    cls = type(
        fn.__name__,
        (Knot,),
        {
            "process": process,
            "__module__": fn.__module__,
            "__qualname__": fn.__qualname__,
            "__doc__": fn.__doc__,
        },
    )
    return KnotFactory(fn=fn, knot_class=cls)


def knot(
    func: Callable[..., Any] | None = None,
) -> Any:
    """Promote a function into a Knot factory.

    The returned object is callable like the original function, but the
    call site constructs a Knot instance::

        @knot
        async def double(x: int) -> int:
            return x * 2

        # Construct an instance — looks like a normal call.
        d = double(x=p, _config=KnotConfig(id="double"))

    Sync functions are auto-wrapped via ``asyncio.to_thread``; the
    function's signature becomes the knot's input contract.

    The factory exposes the original function as ``.fn`` for introspection,
    and the generated Knot subclass as ``.knot_class`` for explicit
    instantiation if needed.
    """
    if func is not None:
        return _make_knot_factory(func)
    return _make_knot_factory


def _pending_record(knot_id: str, exc: BaseException) -> Any:
    """Build a placeholder ExceptionRecord for an Err produced in isolation.

    The engine catches the Err and re-registers the record against the live
    ExceptionManager (which assigns a real id and run_id).  We use a
    placeholder here because at __call__ time the knot has no manager in
    scope — the engine owns that.
    """
    import traceback as _tb

    from pirn.managers.exception_record import ExceptionRecord

    return ExceptionRecord(
        run_id="<unbound>",
        knot_id=knot_id,
        exc_type=type(exc).__name__,
        message=str(exc),
        traceback_text="".join(_tb.format_exception(type(exc), exc, exc.__traceback__)),
    )
