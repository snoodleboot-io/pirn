"""``LithologyClassifier`` — classify lithology along the LAS depth track."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class LithologyClassifier(Knot):
    """Classify lithology using a configured method and append the curve."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"crossplot", "neural_net", "rule_based"}
    )

    def __init__(
        self,
        *,
        las_file: Knot,
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if method not in self.valid_methods:
            raise ValueError(
                f"LithologyClassifier: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        self._method = method
        super().__init__(las_file=las_file, _config=_config, **kwargs)

    async def process(self, las_file: LASFile, **_: Any) -> LASFile:
        return LASFile(
            well_id=las_file.well_id,
            curves=las_file.curves + ("LITH",),
            depth_unit=las_file.depth_unit,
        )
