"""``OptionalMeta`` — metaclass for ``Optional`` that redirects ``isinstance`` checks."""

from __future__ import annotations

from pirn.core.optional_marker import OptionalMarker


class OptionalMeta(type):
    """Metaclass for ``Optional`` that redirects ``isinstance`` checks.

    ``isinstance(x, Optional)`` would normally check whether ``x`` is an
    instance of the ``Optional`` class — but ``Optional.__new__`` never
    returns an ``Optional`` instance; it always returns a ``Knot`` subclass.
    This metaclass overrides ``__instancecheck__`` to check for the
    ``OptionalMarker`` mixin instead, which IS present on every result.
    """

    def __instancecheck__(cls, instance: object) -> bool:
        return isinstance(instance, OptionalMarker)
