"""Source — a knot with no computation parents that produces a value from outside.

Sources are like Parameters but the value is produced by ``process``
rather than supplied via ``RunRequest``.  Examples: read a file, query a
DB, fetch a URL.

Phase 2: one-shot only.  ``process`` returns a single value (or a single
collection).  Streaming sources are deferred to Phase 3 alongside the
trigger/emitter machinery.

Source is a thin subclass of Knot.  Subclasses implement ``process``
with declared parameters for their configuration inputs.  Inputs may be
``Knot | scalar_type``; the framework auto-coerces plain scalars into
``Parameter`` nodes so they participate in the graph with lineage.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot


class Source(Knot):
    """Base class for one-shot sources.

    Subclass and implement ``async def process(self, ...) -> T``.  All
    configuration inputs are declared as ``Knot | scalar_type`` in
    ``__init__`` and as resolved plain types in ``process()``, following
    the standard two-layer knot pattern.

    Example::

        class ReadConfig(Source):
            def __init__(self, *, path: Knot | str, _config: KnotConfig, **kwargs: Any) -> None:
                super().__init__(path=path, _config=_config, **kwargs)

            async def process(self, path: str, **_: Any) -> dict:
                with open(path) as f:
                    return json.load(f)

        with Tapestry() as t:
            cfg = ReadConfig(path="/etc/config.json", _config=KnotConfig(id="config"))
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
