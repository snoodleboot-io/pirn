"""Deprecated compatibility shim for ``pirn.emitters.base``.

``Emitter`` moved to :mod:`pirn.emitters.emitter` so the filename matches
the class it defines (house convention: filename = snake_case(ClassName)).
Import from the new location; this shim is kept for one release cycle and
will be removed afterward.
"""

from __future__ import annotations

import warnings

from pirn.emitters.emitter import Emitter

warnings.warn(
    "'pirn.emitters.base' is deprecated; import 'Emitter' from "
    "'pirn.emitters.emitter' instead. This compatibility shim will be "
    "removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Emitter"]
