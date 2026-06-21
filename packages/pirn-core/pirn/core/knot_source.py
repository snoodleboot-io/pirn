"""KnotSourceRecord — immutable, content-addressed snapshot of a knot's source code.

One ``KnotSourceRecord`` is stored per unique ``(source_text, pirn_version)`` pair.
The same record is shared across every lineage entry that came from identical code,
so the store never accumulates duplicates regardless of how many times a knot runs.

``extract_knot_source`` handles two knot shapes:
- ``@knot``-decorated functions: the decorated function is recovered via
  ``process.__wrapped__`` and the ``@knot`` line is prepended so the stored
  snippet is self-contained.
- Class-based knots (subclasses of ``Knot``): the full class definition is
  captured via ``inspect.getsource``.

Returns ``None`` when source is unavailable (compiled extensions, dynamic
``exec``-created classes, etc.) — callers must treat ``None`` as "source
not recorded" rather than an error.
"""

from __future__ import annotations

import hashlib
import inspect
import textwrap
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    pass


class KnotSourceRecord(BaseModel):
    """Immutable, content-addressed snapshot of a knot's source code.

    Attributes:
        source_hash: SHA-256 hex digest of ``source_text + pirn_version``.
            Used as the primary key in the backing store; guarantees that
            identical code at the same library version maps to exactly one row.
        source_text: Full source of the knot — either the class definition or
            the ``@knot``-decorated function (decorator line included).
        knot_class: Fully-qualified class name at capture time, e.g.
            ``'my_pkg.knots.EnrichUser'``.
        pirn_version: Version of the pirn library at execution time, as
            returned by ``importlib.metadata``.
    """

    model_config = ConfigDict(frozen=True)

    source_hash: str
    source_text: str
    knot_class: str
    pirn_version: str


def extract_knot_source(knot: Any, pirn_version: str) -> KnotSourceRecord | None:
    """Extract the source code of *knot* and return an immutable record.

    Args:
        knot: A ``Knot`` instance whose source should be captured.
        pirn_version: The pirn library version string to embed in the record.

    Returns:
        A ``KnotSourceRecord``, or ``None`` if source is unavailable.
    """
    knot_cls = type(knot)
    try:
        process = getattr(knot_cls, "process", None)
        if process is not None and hasattr(process, "__wrapped__"):
            # @knot-decorated function: getsource on the original function already
            # includes the @knot decorator line as written in the source file.
            source = inspect.getsource(process.__wrapped__)
        else:
            source = inspect.getsource(knot_cls)
    except (OSError, TypeError):
        return None

    source = textwrap.dedent(source)
    knot_class = f"{knot_cls.__module__}.{knot_cls.__qualname__}"
    source_hash = hashlib.sha256((source + pirn_version).encode()).hexdigest()

    return KnotSourceRecord(
        source_hash=source_hash,
        source_text=source,
        knot_class=knot_class,
        pirn_version=pirn_version,
    )
