"""``Optional`` — decorator that makes any knot's failure non-fatal.

Design
------
``Optional`` is a **class decorator**, not a knot subclass.  Calling
``Optional(SomeKnot, _config=..., **kwargs)`` does two things:

1. **Tries to construct** ``SomeKnot(_config=..., **kwargs)``.
2. **On success** — returns the constructed knot, but with its ``__call__``
   replaced by :meth:`Optional._decorated_call`.  The result is an instance
   of ``SomeKnot`` (same class name, same ancestry, one graph node) whose
   runtime failures are silently converted to ``Ok(Skipped(...))``.
3. **On construction failure** — returns a lightweight stub knot (same class
   name, same ID) whose ``process()`` immediately emits ``Skipped`` carrying
   the construction exception in ``detail``.

In both failure paths the original exception is captured and stored in
``Skipped.detail`` so lineage records *why* the skip occurred — "not
configured" looks very different to "network timeout" in the audit trail.

``isinstance(x, Optional)`` works for every outcome via
:class:`_OptionalMeta.__instancecheck__`, which checks for the
:class:`_OptionalMarker` mixin that is applied to all results.

Why not a wrapper knot?
-----------------------
A wrapper knot would add a second node to the graph for every Optional use,
doubling the node count and polluting lineage.  This design keeps the graph
flat — one node per source, Optional semantics baked in.

Why separate ``_OptionalMarker``?
----------------------------------
If ``Optional`` itself appeared in the MRO of the decorated class,
constructing the decorated class would re-trigger ``Optional.__new__``,
causing infinite recursion.  ``_OptionalMarker`` is a plain mixin with no
``__new__``; ``_OptionalMeta.__instancecheck__`` then makes
``isinstance(x, Optional)`` delegate to ``_OptionalMarker``.

Example::

    with Tapestry() as inner:
        file_src = Optional(FileSource, store=store, format=fmt, key=key,
                            _config=KnotConfig(id="src-file"))
        sql_src  = Optional(SqlSource, pool=pool, query=query,
                            _config=KnotConfig(id="src-sql"))
        # file_src and sql_src are FileSource / SqlSource instances —
        # no wrapper nodes — but both are isinstance(..., Optional).
        Aggregator(combine=_first_present, file=file_src, sql=sql_src,
                   _config=KnotConfig(id="agg"))
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.skipped import Skipped


class _OptionalMarker:
    """Plain mixin applied to every Optional-decorated knot or stub.

    Has no logic of its own.  Its sole purpose is to serve as a stable
    marker so that ``isinstance(x, Optional)`` can be answered without
    putting ``Optional`` itself in the decorated class's MRO (which would
    cause ``Optional.__new__`` to fire recursively during construction).

    Do not subclass or instantiate directly.
    """


class _OptionalMeta(type):
    """Metaclass for ``Optional`` that redirects ``isinstance`` checks.

    ``isinstance(x, Optional)`` would normally check whether ``x`` is an
    instance of the ``Optional`` class — but ``Optional.__new__`` never
    returns an ``Optional`` instance; it always returns a ``Knot`` subclass.
    This metaclass overrides ``__instancecheck__`` to check for the
    ``_OptionalMarker`` mixin instead, which IS present on every result.
    """

    def __instancecheck__(cls, instance: object) -> bool:
        return isinstance(instance, _OptionalMarker)


class Optional(metaclass=_OptionalMeta):
    """Decorator that converts any knot construction or runtime failure to ``Ok(Skipped(...))``.

    Not a knot itself.  Returns an instance of the target knot class (or a
    same-named stub) with Optional semantics baked in.

    Parameters
    ----------
    knot_class:
        The knot class to construct and decorate.
    _config:
        ``KnotConfig`` forwarded verbatim to the constructed knot.  The
        ``id`` here is what appears in the graph and in lineage.
    **kwargs:
        All remaining kwargs are forwarded to ``knot_class.__init__``.

    Returns
    -------
    Knot
        Either a decorated ``knot_class`` instance, or a same-named stub —
        both are ``isinstance(..., Optional)``.
    """

    def __new__(
        cls,
        knot_class: type[Knot],
        *,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> Knot:
        try:
            # Build a dynamic subclass of the target that inherits all of its
            # behaviour but overrides __call__ with our error-catching wrapper.
            # We inherit from _OptionalMarker (not Optional) to avoid
            # triggering Optional.__new__ again when this subclass is
            # constructed.
            decorated_cls = type(
                knot_class.__name__,
                (knot_class, _OptionalMarker),
                {"__call__": Optional._decorated_call},
            )
            return decorated_cls(_config=_config, **kwargs)
        except Exception as exc:
            # Construction failed — the caller provided insufficient or
            # invalid config.  Return a stub that registers under the same
            # ID and emits Skipped with the exception detail so lineage
            # shows exactly why this source was not available.
            return Optional._make_stub(knot_class.__name__, exc, _config)

    @classmethod
    def _make_stub(cls, class_name: str, exc: Exception, config: KnotConfig) -> Knot:
        """Return a stub knot that always emits ``Skipped`` carrying the construction error.

        The stub has the same class name and ID as the intended knot so
        that lineage shows ``FileSource(id="src-file") → Skipped`` rather
        than an opaque internal class name.

        Parameters
        ----------
        class_name:
            Name of the class that failed to construct (e.g. ``"FileSource"``).
        exc:
            The exception raised during construction — captured in
            ``Skipped.detail`` for lineage inspection.
        config:
            The original ``KnotConfig`` (preserves the intended knot ID).
        """
        captured = exc

        async def process(self: Any, **_: Any) -> Skipped:
            # self is required for Python's method binding even though
            # the stub ignores all inputs — it always emits the same Skipped.
            return Skipped(
                reason="optional",
                detail={
                    "phase": "construction",
                    "error": type(captured).__name__,
                    "message": str(captured),
                },
            )

        stub_cls = type(class_name, (Knot, _OptionalMarker), {"process": process})
        return stub_cls(_config=config)

    async def _decorated_call(self: Any, parent_results: Mapping[str, Any]) -> Any:
        """Replacement ``__call__`` injected into every successfully decorated knot.

        Wraps the standard ``Knot.__call__`` pipeline — input resolution,
        ``process()`` execution, output validation — but intercepts any
        ``Err`` result and converts it to ``Ok(Skipped(...))``, so the
        engine always records this knot as succeeded, never as failed.

        The original exception is preserved in ``Skipped.detail`` so
        lineage shows *why* the knot skipped (e.g. "file not found",
        "connection refused") rather than a bare skip with no context.

        Parameters
        ----------
        self:
            The decorated knot instance (bound by Python's descriptor
            protocol when this method is stored in the dynamic class dict).
        parent_results:
            Mapping of input name → resolved upstream value, exactly as
            passed by the engine to any ``__call__``.
        """
        from pirn.core.err import Err
        from pirn.core.ok import Ok

        # Delegate to the standard Knot.__call__ pipeline.  This runs
        # input resolution, calls self.process(), validates output, and
        # returns Ok(value) on success or Err on any exception.
        result = await Knot.__call__(self, parent_results)

        if isinstance(result, Err):
            # Convert Err → Ok(Skipped) so the engine records this knot
            # as succeeded.  Downstream knots receive the Skipped value
            # and can decide what to do with it (e.g. Aggregator picks
            # the first non-Skipped parent).
            return Ok(
                value=Skipped(
                    reason="optional",
                    detail={
                        "phase": "execution",
                        "error": result.record.exc_type,
                        "message": result.record.message,
                    },
                )
            )

        return result
