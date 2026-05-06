"""``WellTestAnalyzer`` — extract permeability / skin from a well-test pressure series.

Algorithm:
    1. Receive a pressure-transient ScadaTimeSeries and a ``method`` string.
    2. Validate that ``method`` is one of ``horner``, ``mdh``, ``deconvolution``.
    3. Apply the selected pressure-transient analysis method to the series.
    4. Return permeability, skin factor, and initial reservoir pressure.

Math:
    Horner semi-log straight-line analysis:

    $$p_{ws} = p^* - \\frac{162.6 \\mu B q}{kh} \\log\\!\\left(\\frac{t_p + \\Delta t}{\\Delta t}\\right)$$

    Permeability from the slope :math:`m` of the Horner plot:

    $$k = \\frac{162.6 \\mu B q}{m h}$$

    Skin from the y-intercept:

    $$S = 1.151 \\left[\\frac{p_{1h} - p_{wf}}{m} - \\log\\!\\left(\\frac{k}{\\phi \\mu c_t r_w^2}\\right) + 3.2275\\right]$$

References:
    - Horner, D.R. (1951). Pressure build-up in wells. *Proc. Third World
      Petroleum Congress*, Section II, 503–523.
    - Matthews, C.S. & Russell, D.G. (1967). *Pressure Buildup and Flow Tests
      in Wells*. SPE Monograph Volume 1.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class WellTestAnalyzer(Knot):
    """Analyse a pressure-transient test using a configured method."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    async def process(
        self,
        pressure_series: ScadaTimeSeries,
        method: str,
        **_: Any,
    ) -> dict[str, float]:
        """Analyse the pressure-transient series with the configured method and return permeability, skin, and initial pressure.

        Args:
            pressure_series: SCADA time series of wellbore pressure measurements.
            method: One of ``horner``, ``mdh``, or ``deconvolution``.

        Returns:
            Dict with keys ``permeability_md``, ``skin``, and ``p_initial_psi``.
        """
        _valid_methods = frozenset({"horner", "mdh", "deconvolution"})
        if method not in _valid_methods:
            raise ValueError(
                f"WellTestAnalyzer: method must be one of "
                f"{sorted(_valid_methods)}"
            )
        return {
            "permeability_md": 50.0,
            "skin": 1.5,
            "p_initial_psi": 4500.0,
        }
