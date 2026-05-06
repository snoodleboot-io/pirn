"""Inner deduper used by the medication reconciliation pipeline.

Algorithm:
    1. Receive a tuple of RxCUI code strings from an upstream Knot.
    2. Iterate the codes in order; track codes already seen in a list.
    3. Skip any code that is empty or already present in the seen list.
    4. Return the deduplicated codes as a tuple preserving original order.


References:
    - RxNorm: https://www.nlm.nih.gov/research/umls/rxnorm/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class _DedupRxCUIs(Knot):
    """Inner deduper used by the medication reconciliation pipeline."""

    def __init__(
        self,
        *,
        rxcuis: Knot | tuple[str, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(rxcuis=rxcuis, _config=_config, **kwargs)

    async def process(self, rxcuis: tuple[str, ...], **_: Any) -> tuple[str, ...]:
        """Remove duplicate RxCUI codes while preserving order and filtering empty strings.

        Args:
            rxcuis: The upstream tuple of RxCUI code strings to deduplicate.

        Returns:
            A tuple of unique, non-empty RxCUI codes in their original order.
        """
        seen: list[str] = []
        for code in rxcuis:
            if code and code not in seen:
                seen.append(code)
        return tuple(seen)
