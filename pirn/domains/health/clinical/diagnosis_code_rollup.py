"""``DiagnosisCodeRollup`` — roll ICD-10 codes up to a higher-level prefix.

E.g. ``E11.9`` (type-2 diabetes without complications) rolls up to
``E11`` (type-2 diabetes). The default rollup width is the prefix
before the dot; a custom width can be supplied for finer or coarser
buckets.

Algorithm:
    1. Receive a sequence of ICD-10 code strings and a prefix_length integer.
    2. Validate that codes is a list/tuple of strings and prefix_length is a positive int.
    3. For each code, strip the decimal part and truncate to prefix_length characters.
    4. Return the rolled-up code prefixes as a tuple.


References:
    - ICD-10-CM: https://www.cdc.gov/nchs/icd/icd-10-cm.htm
    - WHO ICD-10: https://icd.who.int/browse10/
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class DiagnosisCodeRollup(Knot):
    """Roll ICD-10 codes up to a higher-level category."""

    def __init__(
        self,
        *,
        codes: Knot | Sequence[str],
        prefix_length: Knot | int = 3,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            codes=codes,
            prefix_length=prefix_length,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        codes: Sequence[str],
        prefix_length: int = 3,
        **_: Any,
    ) -> tuple[str, ...]:
        """Truncate each ICD-10 code to the configured prefix length and return the rolled-up codes.

        Args:
            codes: Sequence of ICD-10 code strings to roll up.
            prefix_length: Number of characters to keep before the decimal.

        Returns:
            A tuple of ICD-10 code prefixes, one per input code.

        Raises:
            TypeError: If codes is not a list/tuple of strings or prefix_length is not int.
            ValueError: If prefix_length is not positive.
        """
        if not isinstance(codes, (list, tuple)):
            raise TypeError(
                "DiagnosisCodeRollup: codes must be a list or tuple"
            )
        for code in codes:
            if not isinstance(code, str):
                raise TypeError(
                    "DiagnosisCodeRollup: every code must be a string"
                )
        if not isinstance(prefix_length, int):
            raise TypeError(
                "DiagnosisCodeRollup: prefix_length must be an int"
            )
        if prefix_length <= 0:
            raise ValueError(
                "DiagnosisCodeRollup: prefix_length must be positive"
            )
        return tuple(
            code.split(".", 1)[0][:prefix_length] for code in codes
        )
