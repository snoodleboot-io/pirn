"""Exception raised when clinical-data quality drops below threshold."""

from __future__ import annotations


class ClinicalDataQualityError(ValueError):
    """Raised when clinical-data quality drops below threshold."""
