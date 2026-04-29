"""Source — a knot with no parents that produces a value from outside.

Sources are like Parameters but the value is produced by ``process``
rather than supplied via ``RunRequest``.  Examples: read a file, query a
DB, fetch a URL.

Phase 2: one-shot only.  ``process`` returns a single value (or a single
collection).  Streaming sources are deferred to Phase 3 alongside the
trigger/emitter machinery.

Source is a thin subclass of Knot.  Subclasses implement ``process``
with no parameters (other than self).  The type of the returned value is
the source's contract.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot


class Source(Knot):
    """Base class for one-shot sources.

    Subclass and implement ``async def process(self) -> T``.  The base
    enforces no parents (sources have none by definition); pass a
    ``_config=KnotConfig(id=...)`` like any other knot.

    Example::

        class ReadConfig(Source):
            async def process(self) -> dict:
                with open("config.json") as f:
                    return json.load(f)

        with Tapestry() as t:
            cfg = ReadConfig(_config=KnotConfig(id="config"))
    """

    def __init__(self, **kwargs: Any) -> None:
        # Sources have no inputs; reject any non-framework kwargs to give
        # a clear error.
        bad = {
            k for k in kwargs
            if k not in {"_config", "tapestry"} and isinstance(kwargs[k], Knot) is not False
        }
        # Actually any non-reserved kwarg is an error for a Source — they
        # take no inputs.
        bad = set(kwargs) - {"_config", "tapestry"}
        if bad:
            raise TypeError(
                f"{type(self).__name__} is a Source and takes no inputs; "
                f"got unexpected kwarg(s) {sorted(bad)!r}"
            )
        super().__init__(**kwargs)
