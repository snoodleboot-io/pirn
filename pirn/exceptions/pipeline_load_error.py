from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class PipelineLoadError(PirnError):
    """Raised when a YAML pipeline definition cannot be loaded or resolved."""
