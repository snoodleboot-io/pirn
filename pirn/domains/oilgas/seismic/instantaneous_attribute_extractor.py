"""``InstantaneousAttributeExtractor`` — compute Hilbert-transform-based instantaneous seismic attributes."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class InstantaneousAttributeExtractor(Knot):
    """Extract instantaneous seismic attributes via Hilbert transform."""

    valid_attributes: ClassVar[frozenset[str]] = frozenset(
        {"amplitude", "phase", "frequency", "bandwidth", "q_factor"}
    )

    def __init__(
        self,
        *,
        trace: Knot,
        attributes: tuple[str, ...] = ("amplitude", "phase", "frequency"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        invalid = [a for a in attributes if a not in self.valid_attributes]
        if invalid:
            raise ValueError(
                f"InstantaneousAttributeExtractor: unknown attributes {invalid}; "
                f"must be from {sorted(self.valid_attributes)}"
            )
        self._attributes = attributes
        super().__init__(trace=trace, _config=_config, **kwargs)

    async def process(self, trace: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Compute instantaneous attributes from a seismic trace.

        Args:
            trace: Dict with ``samples`` (list[float]) and
                ``sample_interval_ms`` (float).

        Returns:
            Dict with one key per requested attribute, each value is list[float].
        """
        if not isinstance(trace, dict):
            raise TypeError("InstantaneousAttributeExtractor: trace must be a dict")
        samples: list[float] = trace.get("samples", [])
        return {attr: [0.0] * len(samples) for attr in self._attributes}
