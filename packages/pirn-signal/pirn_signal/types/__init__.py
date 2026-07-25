"""Signal-domain typed values.

Frames carry lineage metadata only.  Payloads bundle a frame with its
computed data array so both travel together through the transport layer.
Each type is defined in — and imported from — its own concrete module; this
package does not re-export them (house convention forbids import forwarding,
enforced by ``scripts/check_no_import_forwarding.py``).

Frames (metadata):
  ``signal_frame.SignalFrame``, ``spectrum_frame.SpectrumFrame``,
  ``wavelet_frame.WaveletFrame``, ``source_frame.SourceFrame``

Payloads (metadata + data):
  ``signal_payload.SignalPayload``, ``spectrum_payload.SpectrumPayload``,
  ``wavelet_payload.WaveletPayload``, ``source_payload.SourcePayload``
"""
