"""``RxNormNormalizer`` — translate drug names to RxCUI codes via static map.

Same shape as :class:`SnomedCTNormalizer`: caller injects the mapping
so tests are deterministic. A production deployment would replace the
mapping with the RxNorm REST API.

Algorithm:
    1. Receive a sequence of drug name strings and a mapping.
    2. Validate that drug_names is a list/tuple of strings and mapping is a Mapping.
    3. For each name, look up in the mapping (default empty string when unmapped).
    4. Return the RxCUI code strings as a tuple.


References:
    - RxNorm: https://www.nlm.nih.gov/research/umls/rxnorm/
    - NLM RxNorm API: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
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
        drug_names: Knot | Sequence[str],
        mapping: Knot | Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            drug_names=drug_names,
            mapping=mapping,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        drug_names: Sequence[str],
        mapping: Mapping[str, str],
        **_: Any,
    ) -> tuple[str, ...]:
        """Look up each drug name in the mapping and return the corresponding RxCUI code strings.

        Args:
            drug_names: Sequence of drug name strings to translate.
            mapping: Mapping of drug name to RxCUI code string.

        Returns:
            A tuple of RxCUI strings, one per input drug name, or empty string when unmapped.

        Raises:
            TypeError: If drug_names is not a list/tuple of strings or mapping is not a Mapping.
        """
        if not isinstance(drug_names, (list, tuple)):
            raise TypeError("RxNormNormalizer: drug_names must be a list or tuple")
        if not isinstance(mapping, Mapping):
            raise TypeError("RxNormNormalizer: mapping must be a Mapping")
        for name in drug_names:
            if not isinstance(name, str):
                raise TypeError("RxNormNormalizer: every drug name must be a string")
        return tuple(mapping.get(name, "") for name in drug_names)
