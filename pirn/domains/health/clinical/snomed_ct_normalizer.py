"""``SnomedCTNormalizer`` — translate ICD codes to SNOMED CT via static map.

The mapping is caller-injected so tests can supply a deterministic
table. A production deployment would replace the static mapping with a
SNOMED CT terminology service.
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
        codes: Sequence[str],
        mapping: Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._codes = tuple(codes)
        self._mapping = dict(mapping)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[str, ...]:
        return tuple(self._mapping.get(code, "") for code in self._codes)
