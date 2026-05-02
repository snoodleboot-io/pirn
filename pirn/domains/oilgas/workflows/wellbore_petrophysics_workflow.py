"""``WellborePetrophysicsWorkflow`` — full LAS-to-interpreted-logs pipeline.

Composition:
    LAS ingest -> curve validate -> log normalise -> petrophysical eval ->
    porosity -> permeability -> water saturation -> lithology classify.

Construction-time inputs are plain configuration values; the workflow
builds the inner :class:`Tapestry` and wires every knot in
``process()``.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.well.las_curve_validator import LasCurveValidator
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.domains.oilgas.well.lithology_classifier import LithologyClassifier
from pirn.domains.oilgas.well.log_normalizer import LogNormalizer
from pirn.domains.oilgas.well.permeability_estimator import PermeabilityEstimator
from pirn.domains.oilgas.well.petrophysical_evaluator import PetrophysicalEvaluator
from pirn.domains.oilgas.well.porosity_calculator import PorosityCalculator
from pirn.domains.oilgas.well.water_saturation_calculator import (
    WaterSaturationCalculator,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class WellborePetrophysicsWorkflow(SubTapestry):
    """Compose every well knot needed to go from LAS bytes to interpreted logs."""

    def __init__(
        self,
        *,
        file_path: str,
        well_id: str,
        curves: Sequence[str],
        required_curves: Sequence[str],
        target_depth_step: float,
        rw: float,
        matrix_density: float = 2.65,
        fluid_density: float = 1.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(file_path, str) or not file_path:
            raise ValueError(
                "WellborePetrophysicsWorkflow: file_path must be a non-empty string"
            )
        if not isinstance(well_id, str) or not well_id:
            raise ValueError(
                "WellborePetrophysicsWorkflow: well_id must be a non-empty string"
            )
        curve_tuple = tuple(curves)
        required_tuple = tuple(required_curves)
        if not curve_tuple:
            raise ValueError(
                "WellborePetrophysicsWorkflow: curves must be non-empty"
            )
        if not required_tuple:
            raise ValueError(
                "WellborePetrophysicsWorkflow: required_curves must be non-empty"
            )
        self._file_path = file_path
        self._well_id = well_id
        self._curves = curve_tuple
        self._required_curves = required_tuple
        self._target_depth_step = float(target_depth_step)
        self._rw = float(rw)
        self._matrix_density = float(matrix_density)
        self._fluid_density = float(fluid_density)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> RunResult:
        with Tapestry() as inner:
            ingest = LasFileIngester(
                file_path=self._file_path,
                well_id=self._well_id,
                curves=self._curves,
                _config=KnotConfig(id="ingest"),
            )
            validated = LasCurveValidator(
                las_file=ingest,
                required_curves=self._required_curves,
                _config=KnotConfig(id="validate"),
            )
            normalised = LogNormalizer(
                las_file=validated,
                target_depth_step=self._target_depth_step,
                _config=KnotConfig(id="normalise"),
            )
            evaluated = PetrophysicalEvaluator(
                las_file=normalised,
                _config=KnotConfig(id="evaluate"),
            )
            with_porosity = PorosityCalculator(
                las_file=evaluated,
                method="density_neutron",
                matrix_density=self._matrix_density,
                fluid_density=self._fluid_density,
                _config=KnotConfig(id="porosity"),
            )
            with_perm = PermeabilityEstimator(
                las_file=with_porosity,
                method="timur",
                _config=KnotConfig(id="permeability"),
            )
            with_sw = WaterSaturationCalculator(
                las_file=with_perm,
                method="archie",
                rw=self._rw,
                _config=KnotConfig(id="water_saturation"),
            )
            LithologyClassifier(
                las_file=with_sw,
                method="rule_based",
                _config=KnotConfig(id="lithology"),
            )
        return await self._run_inner(inner)
