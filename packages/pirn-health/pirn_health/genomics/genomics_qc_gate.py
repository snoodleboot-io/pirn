"""Backward-compatible import path for ``GenomicsQCGate``.

The real implementation is :class:`~pirn_health.genomics.genomics_qc_check.GenomicsQCCheck`
— assessment knots that return/raise on a quality check use the ``*Check``
suffix, not ``*Gate`` (Rule 7, ``docs/contributing/knot-design-rules.md``;
the framework's own halt primitive is ``pirn.nodes.gate.gate.Gate``). This
module exists only so the pre-rename import path
``pirn_health.genomics.genomics_qc_gate`` keeps resolving.

New code should import :class:`GenomicsQCCheck` from
:mod:`pirn_health.genomics.genomics_qc_check` directly.
"""

from __future__ import annotations

from pirn_health.genomics.genomics_qc_check import GenomicsQCCheck

GenomicsQCGate = GenomicsQCCheck

__all__ = ["GenomicsQCCheck", "GenomicsQCGate"]
