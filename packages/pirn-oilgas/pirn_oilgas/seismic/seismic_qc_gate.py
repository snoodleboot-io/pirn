"""``SeismicQCGate`` — deprecated alias for :class:`SeismicQCCheck`.

``SeismicQCGate`` is an assessment Knot (it returns a QC result dict and
raises on failing datasets), not a pipeline-halting ``Gate`` primitive, so
per the naming rule in ``docs/contributing/knot-design-rules.md`` (Rule 7) it
was renamed to ``SeismicQCCheck`` in ``seismic_qc_check.py``. This module is
kept as a one-class deprecated alias so existing imports keep working for one
deprecation cycle; it emits a ``DeprecationWarning`` on construction and
otherwise behaves identically to :class:`SeismicQCCheck`.
"""

from __future__ import annotations

import warnings
from typing import Any

from pirn_oilgas.seismic.seismic_qc_check import SeismicQCCheck


class SeismicQCGate(SeismicQCCheck):
    """Deprecated alias for :class:`SeismicQCCheck`; emits ``DeprecationWarning``."""

    def __init__(self, **kwargs: Any) -> None:
        warnings.warn(
            "SeismicQCGate is deprecated; use SeismicQCCheck instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(**kwargs)
