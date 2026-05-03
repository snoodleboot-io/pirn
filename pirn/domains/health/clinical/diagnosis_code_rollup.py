"""``DiagnosisCodeRollup`` — roll ICD-10 codes up to a higher-level prefix.

E.g. ``E11.9`` (type-2 diabetes without complications) rolls up to
``E11`` (type-2 diabetes). The default rollup width is the prefix
before the dot; a custom width can be supplied for finer or coarser
buckets.
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
        codes: Sequence[str],
        prefix_length: int = 3,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._codes = tuple(codes)
        self._prefix_length = prefix_length
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[str, ...]:
        """Truncate each ICD-10 code to the configured prefix length and return the rolled-up codes.

        Returns:
            A tuple of ICD-10 code prefixes, one per input code.
        """
        return tuple(
            code.split(".", 1)[0][: self._prefix_length] for code in self._codes
        )
