"""``FeaturePayload`` — named feature metadata bundled with its value array.

Returned by knots that reduce a signal to one or more named scalar features
per channel (entropy, Hurst exponent, correlation dimension, MFCC frames,
etc.) rather than another signal, spectrum, or wavelet decomposition.
``frame`` carries the feature names and channel count; ``data`` is the
feature value array, shaped ``(channel_count, n_features)`` or, for
frame-indexed features such as MFCC, ``(channel_count, n_features, n_frames)``.
"""

from __future__ import annotations

import numpy as np
from pirn.core.payload import Payload

from pirn_signal.types.feature_frame import FeatureFrame


class FeaturePayload(Payload[FeatureFrame, np.ndarray]):
    """Extracted feature set: metadata frame + feature value array."""

    @property
    def frame(self) -> FeatureFrame:
        return self._metadata
