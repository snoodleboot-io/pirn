"""Backward-compatible import path for ``ClinicalDataQualityGate``.

The real implementation is :class:`~pirn_health.clinical.clinical_data_quality_check.ClinicalDataQualityCheck`
— assessment knots that return/raise on a quality check use the ``*Check``
suffix, not ``*Gate`` (Rule 7, ``docs/contributing/knot-design-rules.md``;
the framework's own halt primitive is ``pirn.nodes.gate.gate.Gate``). This
module exists only so the pre-rename import path
``pirn_health.clinical.clinical_data_quality_gate`` keeps resolving.

New code should import :class:`ClinicalDataQualityCheck` from
:mod:`pirn_health.clinical.clinical_data_quality_check` directly.
"""

from __future__ import annotations

from pirn_health.clinical.clinical_data_quality_check import (
    ClinicalDataQualityCheck,
    ClinicalDataQualityError,
)

ClinicalDataQualityGate = ClinicalDataQualityCheck

__all__ = ["ClinicalDataQualityCheck", "ClinicalDataQualityError", "ClinicalDataQualityGate"]
