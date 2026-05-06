"""``LOINCMapper`` — translate lab-test names to LOINC codes via static map.

Production deployments would call the LOINC search API or look up the
loaded LOINC table; this stub takes a caller-injected mapping so tests
are deterministic.

Algorithm:
    1. Receive a sequence of lab test name strings and a mapping.
    2. Validate that lab_test_names is a list/tuple of strings and mapping is a Mapping.
    3. For each name, look up in the mapping (default empty string when unmapped).
    4. Return the LOINC code strings as a tuple.


References:
    - LOINC: https://loinc.org/
    - LOINC API: https://loinc.org/fhir/
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class LOINCMapper(Knot):
    """Translate a sequence of lab-test names to LOINC code strings."""

    def __init__(
        self,
        *,
        lab_test_names: Knot | Sequence[str],
        mapping: Knot | Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            lab_test_names=lab_test_names,
            mapping=mapping,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        lab_test_names: Sequence[str],
        mapping: Mapping[str, str],
        **_: Any,
    ) -> tuple[str, ...]:
        """Look up each lab test name in the mapping and return the corresponding LOINC code strings.

        Args:
            lab_test_names: Sequence of lab test name strings to translate.
            mapping: Mapping of lab test name to LOINC code string.

        Returns:
            A tuple of LOINC code strings, one per input lab test name, or empty string when unmapped.

        Raises:
            TypeError: If lab_test_names is not a list/tuple of strings or mapping is not a Mapping.
        """
        if not isinstance(lab_test_names, (list, tuple)):
            raise TypeError("LOINCMapper: lab_test_names must be a list or tuple")
        if not isinstance(mapping, Mapping):
            raise TypeError("LOINCMapper: mapping must be a Mapping")
        for name in lab_test_names:
            if not isinstance(name, str):
                raise TypeError("LOINCMapper: every lab test name must be a string")
        return tuple(mapping.get(name, "") for name in lab_test_names)
