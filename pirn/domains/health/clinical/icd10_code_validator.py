"""``ICD10CodeValidator`` — bool-valued knot validating ICD-10 strings.

Validates each code against the standard ICD-10-CM regex. A real
deployment would additionally check the code exists in the loaded
ICD-10-CM table; this knot only enforces the structural shape.

Algorithm:
    1. Receive a sequence of ICD-10 code strings.
    2. Validate that codes is a list/tuple of strings.
    3. Match each code against the ICD-10-CM structural regex.
    4. Return True if all codes match, False otherwise.


References:
    - ICD-10-CM: https://www.cdc.gov/nchs/icd/icd-10-cm.htm
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ICD10CodeValidator(Knot):
    """Return ``True`` iff every supplied code matches the ICD-10 pattern."""

    def __init__(
        self,
        *,
        codes: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(codes=codes, _config=_config, **kwargs)

    async def process(
        self,
        codes: Sequence[str],
        **_: Any,
    ) -> bool:
        """Match every code against the ICD-10-CM regex and return True if all match, False otherwise.

        Args:
            codes: Sequence of ICD-10 code strings to validate.

        Returns:
            True if every supplied code matches the ICD-10-CM structural pattern, False otherwise.

        Raises:
            TypeError: If codes is not a list/tuple or contains non-string items.
        """
        if not isinstance(codes, (list, tuple)):
            raise TypeError("ICD10CodeValidator: codes must be a list or tuple")
        for code in codes:
            if not isinstance(code, str):
                raise TypeError("ICD10CodeValidator: every code must be a string")
        icd10_pattern = re.compile(r"^[A-TV-Z][0-9][0-9AB]\.?[0-9A-TV-Z]{0,4}$")
        return all(icd10_pattern.match(code) is not None for code in codes)
