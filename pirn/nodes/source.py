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
    """Base class for one-shot sources that produce a value from outside the pipeline.

    A ``Source`` has no computation parents.  Its value is produced entirely by
    its own ``process()`` implementation, which may read files, query databases,
    fetch URLs, or perform any other I/O.  Configuration knots (e.g. a
    ``Parameter`` carrying a file path) may still be declared as inputs and are
    wired as parents in the DAG so the engine resolves them before calling
    ``process()``.

    Subclass and implement ``async def process(self, ...) -> T``.  All
    configuration inputs are declared as ``Knot | scalar_type`` in
    ``__init__`` and as resolved plain types in ``process()``, following
    the standard two-layer knot pattern.

    Algorithm:
        1. Declaration — subclass declares configuration inputs as
           ``Knot | scalar_type`` in ``__init__``.  Plain scalars are
           auto-coerced to ``Parameter`` nodes by the base ``Knot.__init__``
           so they participate in the DAG with full lineage.
        2. Scheduling — the engine resolves all declared parent knots (config
           inputs and any explicit parents) concurrently before calling
           ``process()``.
        3. Execution — ``process()`` receives resolved plain-Python values for
           all declared inputs and performs the I/O or computation needed to
           produce the source's output value.
        4. Output — the value returned by ``process()`` is wrapped in ``Ok``
           by the engine and made available to downstream knots.

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
