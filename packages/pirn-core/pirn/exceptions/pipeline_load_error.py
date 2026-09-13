from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class PipelineLoadError(PirnError, ValueError):
    """Raised when a YAML pipeline definition cannot be loaded or resolved.

    Subclasses ``ValueError`` in addition to ``PirnError`` — matching the
    precedent set by :class:`~pirn.exceptions.value_evicted_error.ValueEvictedError`
    subclassing ``KeyError`` — because every existing caller of
    :class:`~pirn.yaml_loader.pipeline_loader.PipelineLoader` catches ``ValueError``
    for a malformed pipeline definition. A distinct, more specific type lets
    new code narrow to loader failures without breaking that contract.
    """
