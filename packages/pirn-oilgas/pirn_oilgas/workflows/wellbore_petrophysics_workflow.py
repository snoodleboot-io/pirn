"""``WellborePetrophysicsWorkflow`` — full LAS-to-interpreted-logs pipeline.

Composition:
    LAS assemble -> curve validate -> log normalise -> petrophysical eval ->
    porosity -> permeability -> water saturation -> lithology classify.

Algorithm:
    1. Receive LAS bytes, curve, and petrophysics configuration as
       ``Knot | scalar`` inputs.
    2. Validate all string and numeric inputs in ``process()``.
    3. Build the inner pipeline inside ``process()``:
       - ``LasObjectStoreAssembler``, ``LasCurveValidator``, ``LogNormalizer``,
       - ``PetrophysicalEvaluator``, ``PorosityCalculator``,
       - ``PermeabilityEstimator``, ``WaterSaturationCalculator``,
       - ``LithologyClassifier``.
    4. Return the terminal knot; the base class runs the inner tapestry.


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
from pirn.core.parameter import Parameter
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_oilgas.assemblers.las_object_store_assembler import LasObjectStoreAssembler
from pirn_oilgas.well.las_curve_validator import LasCurveValidator
from pirn_oilgas.well.lithology_classifier import LithologyClassifier
from pirn_oilgas.well.log_normalizer import LogNormalizer
from pirn_oilgas.well.permeability_estimator import PermeabilityEstimator
from pirn_oilgas.well.petrophysical_evaluator import PetrophysicalEvaluator
from pirn_oilgas.well.porosity_calculator import PorosityCalculator
from pirn_oilgas.well.water_saturation_calculator import (
    WaterSaturationCalculator,
)


class WellborePetrophysicsWorkflow(SubTapestry):
    """Compose every well knot needed to go from LAS bytes to interpreted logs."""

    def __init__(
        self,
        *,
        body: Knot,
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
            body=body,
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
        body: bytes,
        well_id: str,
        curves: Sequence[str],
        required_curves: Sequence[str],
        target_depth_step: float,
        rw: float,
        matrix_density: float = 2.65,
        fluid_density: float = 1.0,
        **_: Any,
    ) -> Any:
        """Build the LAS-to-interpreted-logs inner pipeline and return its terminal knot.

        Args:
            body: Raw LAS file bytes from an object store connector.
            well_id: Non-empty well identifier string.
            curves: Non-empty sequence of curve mnemonic strings.
            required_curves: Non-empty sequence of required curve mnemonics.
            target_depth_step: Positive depth sampling step for log normalisation.
            rw: Positive formation water resistivity (ohm·m).
            matrix_density: Positive rock matrix density (g/cm³; default 2.65).
            fluid_density: Positive borehole fluid density (g/cm³; default 1.0).

        Returns:
            Terminal knot of the inner pipeline (``LithologyClassifier``).
        """
        if not isinstance(body, bytes):
            raise TypeError(
                f"WellborePetrophysicsWorkflow: body must be bytes, got {type(body).__name__}"
            )
        if not isinstance(well_id, str) or not well_id:
            raise ValueError("WellborePetrophysicsWorkflow: well_id must be a non-empty string")
        curve_tuple = tuple(curves)
        required_tuple = tuple(required_curves)
        if not curve_tuple:
            raise ValueError("WellborePetrophysicsWorkflow: curves must be non-empty")
        if not required_tuple:
            raise ValueError("WellborePetrophysicsWorkflow: required_curves must be non-empty")
        body_param = Parameter("body", bytes, default=body, _config=KnotConfig(id="body"))
        assembled = LasObjectStoreAssembler(
            body=body_param,
            well_id=well_id,
            curves=curve_tuple,
            _config=KnotConfig(id="assemble"),
        )
        validated = LasCurveValidator(
            payload=assembled,
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
        porosity_result = PorosityCalculator(
            payload=evaluated,
            method="density_neutron",
            matrix_density=matrix_density,
            fluid_density=fluid_density,
            _config=KnotConfig(id="porosity"),
        )
        permeability_result = PermeabilityEstimator(
            payload=porosity_result,
            method="timur",
            _config=KnotConfig(id="permeability"),
        )
        saturation_result = WaterSaturationCalculator(
            payload=permeability_result,
            method="archie",
            rw=rw,
            _config=KnotConfig(id="water_saturation"),
        )
        return LithologyClassifier(
            payload=saturation_result,
            method="rule_based",
            _config=KnotConfig(id="lithology"),
        )
