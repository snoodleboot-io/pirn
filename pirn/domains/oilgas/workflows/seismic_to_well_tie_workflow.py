"""``SeismicToWellTieWorkflow`` — SEG-Y -> header parse -> velocity -> correlate.

Composition:
    SEGY ingest -> header parse -> log ingest (LAS) -> velocity analysis ->
    correlation (stack-extracted trace).
"""

from __future__ import annotations

from typing import Any, Sequence

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
        segy_path: str,
        volume_id: str,
        las_path: str,
        well_id: str,
        las_curves: Sequence[str],
        cmp_inline: int,
        cmp_xline: int,
        initial_velocity_m_s: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(segy_path, str) or not segy_path:
            raise ValueError(
                "SeismicToWellTieWorkflow: segy_path must be a non-empty string"
            )
        if not isinstance(las_path, str) or not las_path:
            raise ValueError(
                "SeismicToWellTieWorkflow: las_path must be a non-empty string"
            )
        las_curve_tuple = tuple(las_curves)
        if not las_curve_tuple:
            raise ValueError(
                "SeismicToWellTieWorkflow: las_curves must be non-empty"
            )
        self._segy_path = segy_path
        self._volume_id = volume_id
        self._las_path = las_path
        self._well_id = well_id
        self._las_curves = las_curve_tuple
        self._cmp_inline = int(cmp_inline)
        self._cmp_xline = int(cmp_xline)
        self._initial_velocity_m_s = float(initial_velocity_m_s)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> RunResult:
        """Build and execute the SEG-Y-to-well-tie inner tapestry and return its RunResult.

        Returns:
            RunResult from the inner pipeline spanning SEG-Y ingest through well-tie correlation.
        """
        with Tapestry() as inner:
            volume = SegyFileIngester(
                file_path=self._segy_path,
                volume_id=self._volume_id,
                _config=KnotConfig(id="segy_ingest"),
            )
            SegyHeaderParser(
                volume=volume,
                _config=KnotConfig(id="header_parse"),
            )
            LasFileIngester(
                file_path=self._las_path,
                well_id=self._well_id,
                curves=self._las_curves,
                _config=KnotConfig(id="log_ingest"),
            )
            gather = CmpGatherExtractor(
                volume=volume,
                cmp_inline=self._cmp_inline,
                cmp_xline=self._cmp_xline,
                _config=KnotConfig(id="cmp_extract"),
            )
            VelocityAnalyzer(
                gather=gather,
                initial_velocity_m_s=self._initial_velocity_m_s,
                _config=KnotConfig(id="velocity"),
            )
            StackProcessor(
                gather=gather,
                _config=KnotConfig(id="correlate"),
            )
        return await self._run_inner(inner)
