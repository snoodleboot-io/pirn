"""Deprecated compatibility shim for ``pirn.streaming.base``.

``StreamingSource`` and ``run_stream`` moved to
:mod:`pirn.streaming.streaming_source` so the filename matches the class it
defines (house convention: filename = snake_case(ClassName)). Import from
the new location; this shim is kept for one release cycle and will be
removed afterward.
"""

from __future__ import annotations

import warnings

from pirn.streaming.streaming_source import StreamingSource, run_stream

warnings.warn(
    "'pirn.streaming.base' is deprecated; import 'StreamingSource' and "
    "'run_stream' from 'pirn.streaming.streaming_source' instead. This "
    "compatibility shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["StreamingSource", "run_stream"]
