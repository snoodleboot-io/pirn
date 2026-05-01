"""Digital Signal Processing knot library.

Install with::

    pip install 'pirn[signal]'
"""

from pirn.domains.extras_loader import ExtrasLoader


ExtrasLoader("signal", ["scipy", "pywt", "librosa"]).require()


__all__: list[str] = []
