"""``RxNormNormalizer`` — translate drug names to RxCUI codes via static map.

Same shape as :class:`SnomedCTNormalizer`: caller injects the mapping
so tests are deterministic. A production deployment would replace the
mapping with the RxNorm REST API.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RxNormNormalizer(Knot):
    """Translate a sequence of drug names to RxNorm RxCUI strings."""

    def __init__(
        self,
        *,
        drug_names: Sequence[str],
        mapping: Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(drug_names, (list, tuple)):
            raise TypeError(
                "RxNormNormalizer: drug_names must be a list or tuple"
            )
        if not isinstance(mapping, Mapping):
            raise TypeError("RxNormNormalizer: mapping must be a Mapping")
        for name in drug_names:
            if not isinstance(name, str):
                raise TypeError(
                    "RxNormNormalizer: every drug name must be a string"
                )
        self._drug_names = tuple(drug_names)
        self._mapping = dict(mapping)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[str, ...]:
        """Look up each drug name in the mapping and return the corresponding RxCUI code strings.

        Returns:
            A tuple of RxCUI strings, one per input drug name, or empty string when unmapped.
        """
        return tuple(self._mapping.get(name, "") for name in self._drug_names)
