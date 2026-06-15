"""``SeismicToWellTieWorkflow`` — SEG-Y -> header parse -> velocity -> correlate.

Composition:
    SEGY assemble -> header parse -> log assemble (LAS) -> velocity analysis ->
    correlation (stack-extracted trace).

Algorithm:
    1. Receive SEG-Y and LAS bytes, volume / well IDs, CMP coordinates,
       curve list, and initial velocity.
    2. Validate all string and numeric inputs in ``process()``.
    3. Build the inner pipeline inside ``process()``:
       - ``SegyObjectStoreAssembler`` and ``SegyHeaderParser`` for volume metadata,
       - ``LasObjectStoreAssembler`` for well log context,
       - ``CmpGatherExtractor`` to isolate the near-well CMP gather,
       - ``VelocityAnalyzer`` for stacking velocity,
       - ``StackProcessor`` to produce the tie trace.
    4. Return the terminal knot; the base class runs the inner tapestry.


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
from pirn.core.parameter import Parameter
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_oilgas.assemblers.las_object_store_assembler import LasObjectStoreAssembler
from pirn_oilgas.assemblers.segy_object_store_assembler import SegyObjectStoreAssembler
from pirn_oilgas.seismic.cmp_gather_extractor import CmpGatherExtractor
from pirn_oilgas.seismic.segy_header_parser import SegyHeaderParser
from pirn_oilgas.seismic.stack_processor import StackProcessor
from pirn_oilgas.seismic.velocity_analyzer import VelocityAnalyzer


class SeismicToWellTieWorkflow(SubTapestry):
    """Tie a synthetic seismogram to a real well log via velocity calibration."""

    def __init__(
        self,
        *,
        segy_body: Knot,
        volume_id: Knot | str,
        las_body: Knot,
        well_id: Knot | str,
        las_curves: Knot | Sequence[str],
        cmp_inline: Knot | int,
        cmp_xline: Knot | int,
        initial_velocity_m_s: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            segy_body=segy_body,
            volume_id=volume_id,
            las_body=las_body,
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
        segy_body: bytes,
        volume_id: str,
        las_body: bytes,
        well_id: str,
        las_curves: Sequence[str],
        cmp_inline: int,
        cmp_xline: int,
        initial_velocity_m_s: float,
        **_: Any,
    ) -> Any:
        """Build the SEG-Y-to-well-tie inner pipeline and return its terminal knot.

        Args:
            segy_body: Raw SEG-Y file bytes from an object store connector.
            volume_id: Non-empty volume identifier string.
            las_body: Raw LAS file bytes from an object store connector.
            well_id: Non-empty well identifier string.
            las_curves: Non-empty sequence of LAS curve mnemonic strings.
            cmp_inline: Non-negative CMP inline index.
            cmp_xline: Non-negative CMP crossline index.
            initial_velocity_m_s: Positive initial velocity guess in m/s.

        Returns:
            Terminal knot of the inner pipeline (``StackProcessor``).
        """
        if not isinstance(segy_body, bytes):
            raise TypeError(
                f"SeismicToWellTieWorkflow: segy_body must be bytes, got {type(segy_body).__name__}"
            )
        if not isinstance(las_body, bytes):
            raise TypeError(
                f"SeismicToWellTieWorkflow: las_body must be bytes, got {type(las_body).__name__}"
            )
        for label, value in (("volume_id", volume_id), ("well_id", well_id)):
            if not isinstance(value, str) or not value:
                raise ValueError(f"SeismicToWellTieWorkflow: {label} must be a non-empty string")
        las_curve_tuple = tuple(las_curves)
        if not las_curve_tuple:
            raise ValueError("SeismicToWellTieWorkflow: las_curves must be non-empty")
        segy_param = Parameter(
            "segy_body", bytes, default=segy_body, _config=KnotConfig(id="segy_body")
        )
        volume = SegyObjectStoreAssembler(
            body=segy_param,
            volume_id=volume_id,
            _config=KnotConfig(id="segy_assemble"),
        )
        SegyHeaderParser(
            volume=volume,
            _config=KnotConfig(id="header_parse"),
        )
        las_param = Parameter(
            "las_body", bytes, default=las_body, _config=KnotConfig(id="las_body")
        )
        LasObjectStoreAssembler(
            body=las_param,
            well_id=well_id,
            curves=las_curve_tuple,
            _config=KnotConfig(id="log_assemble"),
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
        return StackProcessor(
            gather=gather,
            _config=KnotConfig(id="correlate"),
        )
