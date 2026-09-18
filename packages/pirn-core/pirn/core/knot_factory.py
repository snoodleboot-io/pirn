"""``KnotFactory`` and its ``KnotFactory.knot`` decorator.

These live in a separate module from ``Knot`` to keep the core class
lightweight and to allow decorating functions without importing all of
``knot.py``'s runtime machinery.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable, Mapping
from inspect import iscoroutinefunction
from typing import Any

from pirn.core.json_schema_type_builder import JsonSchemaTypeBuilder
from pirn.core.knot import Knot


class KnotFactory:
    """Callable that constructs a ``Knot`` instance per invocation.

    Returned by ``@KnotFactory.knot``.  Calling a factory ``f(**kwargs)`` constructs
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

    @staticmethod
    def __resolvable_annotations(process: Callable[..., Any], fn: Callable[..., Any]) -> None:
        """Make *process*'s annotations resolvable without ``fn``'s ``__globals__``.

        ``functools.wraps`` copies ``fn.__annotations__`` onto the generated
        ``process`` and points ``__wrapped__`` at ``fn``.  ``get_type_hints``
        resolves a wrapped callable's string annotations against the globals of
        the *end* of the ``__wrapped__`` chain, so when ``fn`` carries no
        annotations of its own the generated method keeps this module's
        ``self: Knot, **kwargs: Any -> Any`` — written as strings, because this
        module uses ``from __future__ import annotations`` — and they are then
        resolved against whatever ``fn`` is.  A callable object rather than a
        function (an already-bound value adapted into the ``callable:``
        position of a YAML pipeline) has no ``__globals__`` at all, so ``Knot``
        and ``Any`` came back unresolvable and validation and ``Knot | T``
        coercion were silently off for the generated class (PIR-873).

        Replacing the inherited strings with the objects themselves removes the
        dependency: a hint that is already a type needs no namespace to
        resolve.  ``fn``'s own annotations, when it has any, are left exactly as
        they are -- they are the knot's declared input contract and they resolve
        in ``fn``'s own module.

        Args:
            process: The generated ``process`` method, already wrapped.
            fn: The callable it delegates to.
        """
        if getattr(fn, "__annotations__", None):
            return
        process.__annotations__ = {"self": Knot, "kwargs": Any, "return": Any}

    @staticmethod
    def __make_async_process(fn: Callable[..., Any]) -> Callable[..., Any]:
        # design-decision-override: closure over fn, used as the process() of the dynamic Knot subclass
        @functools.wraps(fn)
        async def process(self: Knot, **kwargs: Any) -> Any:
            return await fn(**kwargs)

        KnotFactory.__resolvable_annotations(process, fn)
        return process

    @staticmethod
    def __make_sync_process(fn: Callable[..., Any]) -> Callable[..., Any]:
        # design-decision-override: closure over fn, used as the process() of the dynamic Knot subclass
        @functools.wraps(fn)
        async def process(self: Knot, **kwargs: Any) -> Any:
            return await asyncio.to_thread(fn, **kwargs)

        KnotFactory.__resolvable_annotations(process, fn)
        return process

    @classmethod
    def create(cls, fn: Callable[..., Any]) -> KnotFactory:
        """Build a KnotFactory for ``fn``, generating the Knot subclass."""
        make_process = (
            cls.__make_async_process if iscoroutinefunction(fn) else cls.__make_sync_process
        )
        knot_cls = type(
            fn.__name__,
            (Knot,),
            {
                "process": make_process(fn),
                "__module__": fn.__module__,
                "__qualname__": fn.__qualname__,
                "__doc__": fn.__doc__,
            },
        )
        return cls(fn=fn, knot_class=knot_cls)

    @classmethod
    def from_schema(
        cls,
        name: str,
        input_schema: Mapping[str, Any],
        process: Callable[..., Any],
        *,
        description: str | None = None,
    ) -> KnotFactory:
        """Build a KnotFactory whose inputs are declared by a JSON schema.

        For a capability that has no Python signature to introspect -- an
        MCP-declared tool, an OpenAPI operation -- the schema plays the role
        ``process()``'s hints play for a hinted knot (ADR agents-speaks-core,
        WS0): its ``properties`` are the declared inputs, ``required`` the
        ones construction must supply, each property's ``default`` fills an
        omitted input, and each fragment becomes the ``TypeAdapter`` that
        ``validate_io`` applies.  ``process`` receives the validated inputs
        by keyword, exactly as a hinted knot does.

        Args:
            name: The generated knot class's name.
            input_schema: A JSON object schema (``type: object`` with a
                ``properties`` mapping).
            process: ``async`` or sync callable taking the inputs by keyword;
                a sync callable runs via ``asyncio.to_thread``.
            description: Docstring for the generated class; defaults to
                ``process.__doc__``.

        Returns:
            A factory constructing instances of the generated class.

        Raises:
            TypeError: If *input_schema* is not an object schema, names a
                framework-reserved property, or requires an undeclared one.
        """
        schema = JsonSchemaTypeBuilder.validate_input_schema(
            input_schema, reserved=Knot.reserved_kwargs()
        )
        make_process = (
            cls.__make_async_process if iscoroutinefunction(process) else cls.__make_sync_process
        )
        knot_cls = type(
            name,
            (Knot,),
            {
                "process": make_process(process),
                "__module__": process.__module__,
                "__qualname__": name,
                "__doc__": description if description is not None else process.__doc__,
                "_input_schema_override": schema,
            },
        )
        return cls(fn=process, knot_class=knot_cls)

    @staticmethod
    def _decorate_with_schema(
        input_schema: Mapping[str, Any], fn: Callable[..., Any]
    ) -> KnotFactory:
        """``@KnotFactory.knot(input_schema=...)``'s decorator body: the function's name names the knot."""
        return KnotFactory.from_schema(fn.__name__, input_schema, fn)

    @staticmethod
    def knot(
        func: Callable[..., Any] | None = None,
        *,
        input_schema: Mapping[str, Any] | None = None,
    ) -> Any:
        """Promote a function into a Knot factory.

        The returned object is callable like the original function, but the
        call site constructs a Knot instance::

            @KnotFactory.knot
            async def double(value: int) -> int:
                return value * 2

            # Construct an instance — looks like a normal call.
            d = double(value=p, _config=KnotConfig(id="double"))

        Sync functions are auto-wrapped via ``asyncio.to_thread``; the
        function's signature becomes the knot's input contract.

        The factory exposes the original function as ``.fn`` for introspection,
        and the generated Knot subclass as ``.knot_class`` for explicit
        instantiation if needed.

        Pass ``input_schema=`` to declare the inputs with a JSON object schema
        instead of the function's signature (``KnotFactory.from_schema``)::

            @KnotFactory.knot(input_schema={"type": "object", "properties": {"q": {"type": "string"}},
                                "required": ["q"]})
            async def search(**arguments: Any) -> list[str]:
                ...
        """
        if input_schema is not None:
            if func is not None:
                return KnotFactory.from_schema(func.__name__, input_schema, func)
            return functools.partial(KnotFactory._decorate_with_schema, input_schema)
        if func is not None:
            return KnotFactory.create(func)
        return KnotFactory.create
