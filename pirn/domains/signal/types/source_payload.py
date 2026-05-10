"""``SourcePayload`` — source-separation metadata bundled with separated source arrays.

Returned by knots that decompose a mixed signal into independent sources
(ICA, NMF, PCA, SSA, sparse decomposition, etc.).  ``frame`` carries the
source count and mixing matrix shape; ``data`` is a 2-D array shaped
``(n_sources, n_samples)`` where each row is one recovered source signal.
"""

from __future__ import annotations

import numpy as np

from pirn.core.payload import Payload
from pirn.domains.signal.types.source_frame import SourceFrame


class SourcePayload(Payload[SourceFrame, np.ndarray]):
    """Source-separated signal: metadata frame + separated source array."""

    @property
    def frame(self) -> SourceFrame:
        return self._metadata
