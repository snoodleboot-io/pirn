"""``WellborePetrophysicsWorkflow`` — full LAS-to-interpreted-logs pipeline.

Composition:
    LAS ingest -> curve validate -> log normalise -> petrophysical eval ->
    porosity -> permeability -> water saturation -> lithology classify.

Construction-time inputs are plain configuration values; the workflow
builds the inner :class:`Tapestry` and wires every knot in
``process()``.

Algorithm:
    1. Receive all LAS file, curve, and petrophysics configuration as
       ``Knot | scalar`` inputs.
    2. Validate all string and numeric inputs in ``process()``.
    3. Build and wire an inner ``Tapestry`` with:
       - ``LasFileIngester``, ``LasCurveValidator``, ``LogNormalizer``,
       - ``PetrophysicalEvaluator``, ``PorosityCalculator``,
       - ``PermeabilityEstimator``, ``WaterSaturationCalculator``,
       - ``LithologyClassifier``.
    4. Execute the inner tapestry and return the ``RunResult``.


References:
    - Archie, G.E. (1942). The electrical resistivity log as an aid in
      determining some reservoir characteristics. *Trans. AIME*, 146,
      54-62. SPE-942054-G.
    - LAS 2.0 File Format Standard (1992), Canadian Well Logging Society.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
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
        file_path: Knot | str,
        well_id: Knot | str,
        curves: Knot | Sequence[str],
        required_curves: Knot | Sequence[str],
        target_depth_step: Knot | float,
        rw: Knot | float,
        matrix_density: Knot | float = 2.65,
        fluid_density: Knot | float = 1.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            file_path=file_path,
            well_id=well_id,
            curves=curves,
            required_curves=required_curves,
            target_depth_step=target_depth_step,
            rw=rw,
            matrix_density=matrix_density,
            fluid_density=fluid_density,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        file_path: str,
        well_id: str,
        curves: Sequence[str],
        required_curves: Sequence[str],
        target_depth_step: float,
        rw: float,
        matrix_density: float = 2.65,
        fluid_density: float = 1.0,
        **_: Any,
    ) -> RunResult:
        """Build and execute the LAS-to-interpreted-logs inner tapestry and return its RunResult.

        Args:
            file_path: Non-empty path to the LAS file on disk.
            well_id: Non-empty well identifier string.
            curves: Non-empty sequence of curve mnemonic strings.
            required_curves: Non-empty sequence of required curve mnemonics.
            target_depth_step: Positive depth sampling step for log normalisation.
            rw: Positive formation water resistivity (ohm·m).
            matrix_density: Positive rock matrix density (g/cm³; default 2.65).
            fluid_density: Positive borehole fluid density (g/cm³; default 1.0).

        Returns:
            RunResult from the inner pipeline spanning LAS ingest through lithology classification.
        """
        if not isinstance(file_path, str) or not file_path:
            raise ValueError("WellborePetrophysicsWorkflow: file_path must be a non-empty string")
        if not isinstance(well_id, str) or not well_id:
            raise ValueError("WellborePetrophysicsWorkflow: well_id must be a non-empty string")
        curve_tuple = tuple(curves)
        required_tuple = tuple(required_curves)
        if not curve_tuple:
            raise ValueError("WellborePetrophysicsWorkflow: curves must be non-empty")
        if not required_tuple:
            raise ValueError("WellborePetrophysicsWorkflow: required_curves must be non-empty")
        with Tapestry() as inner:
            ingest = LasFileIngester(
                file_path=file_path,
                well_id=well_id,
                curves=curve_tuple,
                _config=KnotConfig(id="ingest"),
            )
            validated = LasCurveValidator(
                payload=ingest,
                required_curves=required_tuple,
                _config=KnotConfig(id="validate"),
            )
            normalised = LogNormalizer(
                payload=validated,
                target_depth_step=target_depth_step,
                _config=KnotConfig(id="normalise"),
            )
            evaluated = PetrophysicalEvaluator(
                payload=normalised,
                _config=KnotConfig(id="evaluate"),
            )
            with_porosity = PorosityCalculator(
                payload=evaluated,
                method="density_neutron",
                matrix_density=matrix_density,
                fluid_density=fluid_density,
                _config=KnotConfig(id="porosity"),
            )
            with_perm = PermeabilityEstimator(
                payload=with_porosity,
                method="timur",
                _config=KnotConfig(id="permeability"),
            )
            with_sw = WaterSaturationCalculator(
                payload=with_perm,
                method="archie",
                rw=rw,
                _config=KnotConfig(id="water_saturation"),
            )
            LithologyClassifier(
                payload=with_sw,
                method="rule_based",
                _config=KnotConfig(id="lithology"),
            )
        return await self._run_inner(inner)
