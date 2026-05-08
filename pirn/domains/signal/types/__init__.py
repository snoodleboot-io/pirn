"""Signal-domain typed values.

Frames carry lineage metadata only.  Payloads bundle a frame with its
computed data array so both travel together through the transport layer.

Frames (metadata):
  SignalFrame, SpectrumFrame, WaveletFrame, SourceFrame

Payloads (metadata + data):
  SignalPayload, SpectrumPayload, WaveletPayload, SourcePayload
"""

from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.source_frame import SourceFrame
from pirn.domains.signal.types.source_payload import SourcePayload
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.domains.signal.types.spectrum_payload import SpectrumPayload
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.types.wavelet_payload import WaveletPayload

__all__ = [
    "SignalFrame",
    "SignalPayload",
    "SourceFrame",
    "SourcePayload",
    "SpectrumFrame",
    "SpectrumPayload",
    "WaveletFrame",
    "WaveletPayload",
]
