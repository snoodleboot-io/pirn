"""``SeismicToWellTieWorkflow`` — SEG-Y -> header parse -> velocity -> correlate.

Composition:
    SEGY ingest -> header parse -> log ingest (LAS) -> velocity analysis ->
    correlation (stack-extracted trace).

Algorithm:
    1. Receive SEG-Y and LAS file paths, volume / well IDs, CMP coordinates,
       curve list, and initial velocity.
    2. Validate all string and numeric inputs in ``process()``.
    3. Build and wire an inner ``Tapestry`` with:
       - ``SegyFileIngester`` and ``SegyHeaderParser`` for volume metadata,
       - ``LasFileIngester`` for well log context,
       - ``CmpGatherExtractor`` to isolate the near-well CMP gather,
       - ``VelocityAnalyzer`` for stacking velocity,
       - ``StackProcessor`` to produce the tie trace.
    4. Execute the inner tapestry and return the ``RunResult``.


References:
    - White, R.E. (1980). Partial coherence matching of synthetic seismograms
      with seismic traces. *Geophysical Prospecting*, 28(3), 333-358.
    - Simm, R. & Bacon, M. (2014). *Seismic Amplitude: An Interpreter's
      Handbook*. Cambridge University Press, Chapter 3 (well-to-seismic tie).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.seismic.cmp_gather_extractor import CmpGatherExtractor
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.seismic.segy_header_parser import SegyHeaderParser
from pirn.domains.oilgas.seismic.stack_processor import StackProcessor
from pirn.domains.oilgas.seismic.velocity_analyzer import VelocityAnalyzer
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class SeismicToWellTieWorkflow(SubTapestry):
    """Tie a synthetic seismogram to a real well log via velocity calibration."""

    def __init__(
        self,
        *,
        segy_path: Knot | str,
        volume_id: Knot | str,
        las_path: Knot | str,
        well_id: Knot | str,
        las_curves: Knot | Sequence[str],
        cmp_inline: Knot | int,
        cmp_xline: Knot | int,
        initial_velocity_m_s: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            segy_path=segy_path,
            volume_id=volume_id,
            las_path=las_path,
            well_id=well_id,
            las_curves=las_curves,
            cmp_inline=cmp_inline,
            cmp_xline=cmp_xline,
            initial_velocity_m_s=initial_velocity_m_s,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        segy_path: str,
        volume_id: str,
        las_path: str,
        well_id: str,
        las_curves: Sequence[str],
        cmp_inline: int,
        cmp_xline: int,
        initial_velocity_m_s: float,
        **_: Any,
    ) -> RunResult:
        """Build and execute the SEG-Y-to-well-tie inner tapestry and return its RunResult.

        Args:
            segy_path: Non-empty path to the SEG-Y file on disk.
            volume_id: Non-empty volume identifier string.
            las_path: Non-empty path to the LAS file on disk.
            well_id: Non-empty well identifier string.
            las_curves: Non-empty sequence of LAS curve mnemonic strings.
            cmp_inline: Non-negative CMP inline index.
            cmp_xline: Non-negative CMP crossline index.
            initial_velocity_m_s: Positive initial velocity guess in m/s.

        Returns:
            RunResult from the inner pipeline spanning SEG-Y ingest through well-tie correlation.
        """
        for label, value in (
            ("segy_path", segy_path),
            ("las_path", las_path),
            ("volume_id", volume_id),
            ("well_id", well_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"SeismicToWellTieWorkflow: {label} must be a non-empty string"
                )
        las_curve_tuple = tuple(las_curves)
        if not las_curve_tuple:
            raise ValueError(
                "SeismicToWellTieWorkflow: las_curves must be non-empty"
            )
        with Tapestry() as inner:
            volume = SegyFileIngester(
                file_path=segy_path,
                volume_id=volume_id,
                _config=KnotConfig(id="segy_ingest"),
            )
            SegyHeaderParser(
                volume=volume,
                _config=KnotConfig(id="header_parse"),
            )
            LasFileIngester(
                file_path=las_path,
                well_id=well_id,
                curves=las_curve_tuple,
                _config=KnotConfig(id="log_ingest"),
            )
            gather = CmpGatherExtractor(
                volume=volume,
                cmp_inline=cmp_inline,
                cmp_xline=cmp_xline,
                _config=KnotConfig(id="cmp_extract"),
            )
            VelocityAnalyzer(
                gather=gather,
                initial_velocity_m_s=initial_velocity_m_s,
                _config=KnotConfig(id="velocity"),
            )
            StackProcessor(
                gather=gather,
                _config=KnotConfig(id="correlate"),
            )
        return await self._run_inner(inner)
