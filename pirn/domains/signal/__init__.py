"""Digital Signal Processing knot library.

Install with::

    pip install 'pirn[signal]'

Covers spectral analysis, IIR/FIR filtering, wavelets, adaptive filtering,
state estimation (Kalman/UKF/particle), source separation, and audio/speech.
See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog.
"""

from pirn.domains._extras import require_extra

require_extra("signal", ["scipy", "pywt", "librosa"])

__all__: list[str] = []
