"""``OptionalMarker`` — plain mixin applied to every Optional-decorated knot or stub."""

from __future__ import annotations


class OptionalMarker:
    """Plain mixin applied to every Optional-decorated knot or stub.

    Has no logic of its own.  Its sole purpose is to serve as a stable
    marker so that ``isinstance(x, Optional)`` can be answered without
    putting ``Optional`` itself in the decorated class's MRO (which would
    cause ``Optional.__new__`` to fire recursively during construction).

    Do not subclass or instantiate directly.
    """
