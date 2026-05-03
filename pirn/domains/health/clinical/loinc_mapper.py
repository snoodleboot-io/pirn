"""``LOINCMapper`` — translate lab-test names to LOINC codes via static map.

Production deployments would call the LOINC search API or look up the
loaded LOINC table; this stub takes a caller-injected mapping so tests
are deterministic.
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
        lab_test_names: Sequence[str],
        mapping: Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(lab_test_names, (list, tuple)):
            raise TypeError(
                "LOINCMapper: lab_test_names must be a list or tuple"
            )
        if not isinstance(mapping, Mapping):
            raise TypeError("LOINCMapper: mapping must be a Mapping")
        for name in lab_test_names:
            if not isinstance(name, str):
                raise TypeError(
                    "LOINCMapper: every lab test name must be a string"
                )
        self._lab_test_names = tuple(lab_test_names)
        self._mapping = dict(mapping)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[str, ...]:
        """Look up each lab test name in the mapping and return the corresponding LOINC code strings.

        Returns:
            A tuple of LOINC code strings, one per input lab test name, or empty string when unmapped.
        """
        return tuple(
            self._mapping.get(name, "") for name in self._lab_test_names
        )
