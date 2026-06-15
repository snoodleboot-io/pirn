"""Digital Signal Processing knot library.

Install with::

    pip install 'pirn-signal[signal]'

The core orchestration layer (types and the slim ``Knot`` stubs under
``spectral``, ``filters``, ``wavelets``, ``adaptive``, ``statistical``,
``separation``, ``nonlinear``, ``resampling``, ``audio``) is pure-Python
and importable without ``scipy`` / ``pywavelets`` / ``librosa``. Concrete
DSP backends will instantiate
:class:`pirn_signal.extras_loader.ExtrasLoader` at the call boundary so
the missing-extras error fires only when a real implementation is used.
"""

# Pure-Python orchestration layer; no module-level dependencies on
# scipy, pywavelets, or librosa. See module docstring above.

import warnings

from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SweetTeaWarning)
    Registry.fill_registry(module=__name__, library="pirn")

__all__: list[str] = []
