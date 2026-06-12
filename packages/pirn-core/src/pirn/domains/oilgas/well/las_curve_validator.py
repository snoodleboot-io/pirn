"""``LasCurveValidator`` — assert required curves are present in a LAS payload.

Algorithm:
    1. Receive a LASPayload and a non-empty sequence of required curve
       mnemonics.
    2. Validate that ``required_curves`` is non-empty and every element is a
       non-empty string.
    3. Compare the required curve list against the curves present in the
       payload's ``curve_data`` mapping (the authoritative truth of what is
       actually loaded).
    4. Raise ``ValueError`` for any missing curve; otherwise pass the payload
       through unchanged.


References:
    - LAS 2.0 File Format Standard (1992), Canadian Well Logging Society
      (curve mnemonic and unit conventions).
    - API Recommended Practice 40 (1998) — Recommended Practice for Core
      Analysis, Section 1.2 (log-curve labelling).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_payload import LASPayload


class LasCurveValidator(Knot):
    """Validate that a LASPayload contains every required curve."""

    def __init__(
        self,
        *,
        payload: Knot,
        required_curves: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            payload=payload,
            required_curves=required_curves,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        payload: LASPayload,
        required_curves: Sequence[str],
        **_: Any,
    ) -> LASPayload:
        """Validate that all required curves are present in the payload and return it unchanged.

        Args:
            payload: LASPayload whose ``curve_data`` keys are validated.
            required_curves: Non-empty sequence of required curve mnemonic strings.

        Returns:
            The same LASPayload passed in, unchanged.

        Raises:
            ValueError: If any required curve is absent from ``payload.curve_data``.
        """
        required_tuple = tuple(required_curves)
        if not required_tuple:
            raise ValueError("LasCurveValidator: required_curves must be non-empty")
        for curve in required_tuple:
            if not isinstance(curve, str) or not curve:
                raise ValueError(
                    "LasCurveValidator: every required curve must be a non-empty string"
                )
        present = set(payload.curve_data.keys())
        missing = [c for c in required_tuple if c not in present]
        if missing:
            raise ValueError(
                f"LasCurveValidator({payload.las.well_id!r}): missing required curve(s) {missing!r}"
            )
        return payload
