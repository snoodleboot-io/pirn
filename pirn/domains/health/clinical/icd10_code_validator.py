"""``ICD10CodeValidator`` — bool-valued knot validating ICD-10 strings.

Validates each code against the standard ICD-10-CM regex. A real
deployment would additionally check the code exists in the loaded
ICD-10-CM table; this knot only enforces the structural shape.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ICD10CodeValidator(Knot):
    """Return ``True`` iff every supplied code matches the ICD-10 pattern."""

    _icd10_pattern = re.compile(r"^[A-TV-Z][0-9][0-9AB]\.?[0-9A-TV-Z]{0,4}$")

    def __init__(
        self,
        *,
        codes: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(codes, (list, tuple)):
            raise TypeError(
                "ICD10CodeValidator: codes must be a list or tuple"
            )
        for code in codes:
            if not isinstance(code, str):
                raise TypeError(
                    "ICD10CodeValidator: every code must be a string"
                )
        self._codes = tuple(codes)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> bool:
        return all(
            self._icd10_pattern.match(code) is not None for code in self._codes
        )
