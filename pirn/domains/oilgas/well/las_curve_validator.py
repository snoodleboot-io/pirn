"""``LasCurveValidator`` — assert required curves are present in a LAS file."""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class LasCurveValidator(Knot):
    """Validate that a parsed LAS file contains every required curve."""

    def __init__(
        self,
        *,
        las_file: Knot,
        required_curves: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._required_curves = required_tuple
        super().__init__(las_file=las_file, _config=_config, **kwargs)

    async def process(self, las_file: LASFile, **_: Any) -> LASFile:
        """Validate that all required curves are present in the LAS file and return it unchanged.

        Args:
            las_file: Parsed LAS file whose curve set is validated.

        Returns:
            The same LASFile passed in, unchanged.

        Raises:
            ValueError: If any required curve is absent from the LAS file.
        """
        present = set(las_file.curves)
        missing = [c for c in self._required_curves if c not in present]
        if missing:
            raise ValueError(
                f"LasCurveValidator({las_file.well_id!r}): missing required "
                f"curve(s) {missing!r}"
            )
        return las_file
