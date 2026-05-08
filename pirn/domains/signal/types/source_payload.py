"""``SourcePayload`` — source-separation metadata bundled with separated source arrays.

Returned by knots that decompose a mixed signal into independent sources
(ICA, NMF, PCA, SSA, sparse decomposition, etc.).  ``frame`` carries the
source count and mixing matrix shape; ``data`` is a 2-D array shaped
``(n_sources, n_samples)`` where each row is one recovered source signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.signal.types.source_frame import SourceFrame


@dataclass
class SourcePayload(PirnOpaqueValue):
    """Source-separated signal: metadata frame + separated source array."""

    frame: SourceFrame
    data: np.ndarray

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            **self.frame._pirn_audit_dict(),
            "data_shape": list(self.data.shape),
            "data_dtype": str(self.data.dtype),
        }
