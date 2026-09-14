"""``RepeatBeamForExpansion`` — flatten the beam for expansion fan-out."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RepeatBeamForExpansion(Knot):
    """Flatten the beam into one entry per ``(path, candidate index)`` pair."""

    def __init__(
        self,
        *,
        beam: Knot | list[tuple[str, float]],
        k_candidates: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(beam=beam, k_candidates=k_candidates, _config=_config, **kwargs)

    async def process(
        self, beam: list[tuple[str, float]], k_candidates: int, **_: Any
    ) -> list[str]:
        """Repeat each beam path ``k_candidates`` times, flattened.

        Args:
            beam: The current beam, as ``(path, score)`` pairs.
            k_candidates: Number of next-thoughts to request per path.

        Returns:
            A flat list of parent paths, each repeated ``k_candidates`` times.
        """
        return [path for path, _score in beam for _ in range(k_candidates)]
