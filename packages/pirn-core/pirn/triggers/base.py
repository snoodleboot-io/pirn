"""Deprecated compatibility shim for ``pirn.triggers.base``.

``Trigger`` and ``run_forever`` moved to :mod:`pirn.triggers.trigger` so the
filename matches the class it defines (house convention: filename =
snake_case(ClassName)). Import from the new location; this shim is kept for
one release cycle and will be removed afterward.
"""

from __future__ import annotations

import warnings

from pirn.triggers.trigger import Trigger, run_forever

warnings.warn(
    "'pirn.triggers.base' is deprecated; import 'Trigger' and 'run_forever' "
    "from 'pirn.triggers.trigger' instead. This compatibility shim will be "
    "removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Trigger", "run_forever"]
