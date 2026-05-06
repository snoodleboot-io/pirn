"""``LasCurveValidator`` — assert required curves are present in a LAS file.

Algorithm:
    1. Receive a parsed LAS file and a non-empty sequence of required curve
       mnemonics.
    2. Validate that ``required_curves`` is non-empty and every element is a
       non-empty string.
    3. Compare the required curve list against the curves present in the
       LAS file.
    4. Raise ``ValueError`` for any missing curve; otherwise pass the LAS
       file through unchanged.


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
from pirn.domains.oilgas.types.las_file import LASFile


class LasCurveValidator(Knot):
    """Validate that a parsed LAS file contains every required curve."""

    def __init__(
        self,
        *,
        las_file: Knot,
        required_curves: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            las_file=las_file,
            required_curves=required_curves,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        las_file: LASFile,
        required_curves: Sequence[str],
        **_: Any,
    ) -> LASFile:
        """Validate that all required curves are present in the LAS file and return it unchanged.

        Args:
            las_file: Parsed LAS file whose curve set is validated.
            required_curves: Non-empty sequence of required curve mnemonic strings.

        Returns:
            The same LASFile passed in, unchanged.

        Raises:
            ValueError: If any required curve is absent from the LAS file.
        """
        required_tuple = tuple(required_curves)
        if not required_tuple:
            raise ValueError(
                "LasCurveValidator: required_curves must be non-empty"
            )
        for curve in required_tuple:
            if not isinstance(curve, str) or not curve:
                raise ValueError(
                    "LasCurveValidator: every required curve must be a non-empty string"
                )
        present = set(las_file.curves)
        missing = [c for c in required_tuple if c not in present]
        if missing:
            raise ValueError(
                f"LasCurveValidator({las_file.well_id!r}): missing required "
                f"curve(s) {missing!r}"
            )
        return las_file
