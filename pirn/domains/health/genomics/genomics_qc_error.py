"""Exception raised when genomics QC metrics fall below threshold."""

from __future__ import annotations


class GenomicsQCError(ValueError):
    """Raised when genomics QC metrics fall below threshold."""
