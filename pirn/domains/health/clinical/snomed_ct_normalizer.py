"""``SnomedCTNormalizer`` — translate ICD codes to SNOMED CT via static map.

The mapping is caller-injected so tests can supply a deterministic
table. A production deployment would replace the static mapping with a
SNOMED CT terminology service.

Algorithm:
    1. Receive a sequence of ICD code strings and a mapping.
    2. Validate that codes is a list/tuple of strings and mapping is a Mapping.
    3. For each code, look up in the mapping (default empty string when unmapped).
    4. Return the SNOMED CT identifier strings as a tuple.


References:
    - SNOMED CT: https://www.snomed.org/
    - SNOMED CT Browser: https://browser.ihtsdotools.org/
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SnomedCTNormalizer(Knot):
    """Translate a sequence of ICD codes to SNOMED CT identifiers."""

    def __init__(
        self,
        *,
        codes: Knot | Sequence[str],
        mapping: Knot | Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            codes=codes,
            mapping=mapping,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        codes: Sequence[str],
        mapping: Mapping[str, str],
        **_: Any,
    ) -> tuple[str, ...]:
        """Look up each ICD code in the mapping and return the corresponding SNOMED CT identifier strings.

        Args:
            codes: Sequence of ICD code strings to translate.
            mapping: Mapping of ICD code to SNOMED CT identifier string.

        Returns:
            A tuple of SNOMED CT identifier strings, one per input code, or empty string when unmapped.

        Raises:
            TypeError: If codes is not a list/tuple of strings or mapping is not a Mapping.
        """
        if not isinstance(codes, (list, tuple)):
            raise TypeError(
                "SnomedCTNormalizer: codes must be a list or tuple"
            )
        if not isinstance(mapping, Mapping):
            raise TypeError(
                "SnomedCTNormalizer: mapping must be a Mapping"
            )
        for code in codes:
            if not isinstance(code, str):
                raise TypeError(
                    "SnomedCTNormalizer: every code must be a string"
                )
        return tuple(mapping.get(code, "") for code in codes)
