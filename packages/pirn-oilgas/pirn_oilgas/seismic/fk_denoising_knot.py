"""``FKDenoisingKnot`` — F-K domain noise attenuation for seismic gathers.

Algorithm:
    1. Receive a gather dict, a positive ``velocity_threshold_m_s``, and a
       ``taper_width_pct`` in (0, 50].
    2. Validate all numeric inputs.
    3. Transform each trace to the 2-D F-K domain using a 2-D FFT.
    4. Apply a fan (pie-slice) mute below ``velocity_threshold_m_s`` with
       a cosine taper of width ``taper_width_pct`` percent.
    5. Inverse-transform back to the time-offset domain.
    6. Return the denoised traces and the noise model parameters.

Math:
    F-K fan filter rejection criterion for wavenumber :math:`k_x` at
    frequency :math:`f`:

    $$v_{apparent} = \\frac{f}{k_x} < v_{threshold}
      \\implies \\text{reject}$$

    Cosine taper weight in the transition band:

    $$w = \\frac{1}{2}\\left(1 - \\cos\\!\\left(\\pi \\frac{v - v_0}{\\Delta v}
      \\right)\\right)$$

References:
    - Yilmaz, Ö. (2001). *Seismic Data Analysis*, 2nd ed. SEG,
      Chapter 6 (F-K filtering and ground-roll attenuation).
    - Treitel, S. & Lines, L. (2001). Past, present, and future of geophysical
      inversion — a new millennium analysis. *Geophysics*, 66(1), 21-24.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class FKDenoisingKnot(Knot):
    """Attenuate coherent noise in the frequency-wavenumber domain."""

    def __init__(
        self,
        *,
        gather: Knot,
        velocity_threshold_m_s: Knot | float,
        taper_width_pct: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            gather=gather,
            velocity_threshold_m_s=velocity_threshold_m_s,
            taper_width_pct=taper_width_pct,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        gather: dict[str, Any],
        velocity_threshold_m_s: float,
        taper_width_pct: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Apply F-K filter to attenuate noise below the velocity threshold.

        Args:
            gather: Dict with ``traces`` (list of dicts with ``offset_m``
                and ``samples``).
            velocity_threshold_m_s: Positive apparent-velocity reject boundary (m/s).
            taper_width_pct: Taper width as a percentage of the reject boundary
                in (0, 50].

        Returns:
            Dict with ``denoised_traces`` (list) and ``noise_model`` (dict).
        """
        if not isinstance(velocity_threshold_m_s, (int, float)):
            raise TypeError("FKDenoisingKnot: velocity_threshold_m_s must be numeric")
        if velocity_threshold_m_s <= 0:
            raise ValueError("FKDenoisingKnot: velocity_threshold_m_s must be positive")
        if not isinstance(taper_width_pct, (int, float)):
            raise TypeError("FKDenoisingKnot: taper_width_pct must be numeric")
        if not (0 < taper_width_pct <= 50):
            raise ValueError("FKDenoisingKnot: taper_width_pct must be in (0, 50]")
        if not isinstance(gather, dict):
            raise TypeError("FKDenoisingKnot: gather must be a dict")
        traces: list[dict[str, Any]] = gather.get("traces", [])
        if not traces:
            return {
                "denoised_traces": traces,
                "noise_model": {
                    "velocity_threshold_m_s": float(velocity_threshold_m_s),
                    "taper_width_pct": float(taper_width_pct),
                },
            }

        n_traces = len(traces)
        n_samples = max(len(tr.get("samples", [])) for tr in traces)
        if n_samples == 0:
            return {
                "denoised_traces": traces,
                "noise_model": {
                    "velocity_threshold_m_s": float(velocity_threshold_m_s),
                    "taper_width_pct": float(taper_width_pct),
                },
            }

        dt = float(gather.get("sample_interval_ms", 4.0)) * 1e-3
        dx = float(gather.get("trace_spacing_m", 25.0))

        data_matrix = np.zeros((n_samples, n_traces), dtype=np.float64)
        offsets_m: list[float] = []
        for trace_idx, tr in enumerate(traces):
            samps = tr.get("samples", [])
            data_matrix[: len(samps), trace_idx] = samps
            offsets_m.append(float(tr.get("offset_m", trace_idx * dx)))

        fk = np.fft.fft2(data_matrix)
        freqs = np.fft.fftfreq(n_samples, d=dt)
        kxs = np.fft.fftfreq(n_traces, d=dx)

        taper_frac = taper_width_pct / 100.0
        v_thr = float(velocity_threshold_m_s)
        v_taper_lo = v_thr * (1.0 - taper_frac)

        mask = np.ones((n_samples, n_traces), dtype=np.float64)
        for freq_idx, freq in enumerate(freqs):
            for kx_idx, kx in enumerate(kxs):
                if abs(kx) < 1e-12:
                    continue
                v_app = abs(freq / kx)
                if v_app >= v_thr:
                    mask[freq_idx, kx_idx] = 1.0
                elif v_app <= v_taper_lo:
                    mask[freq_idx, kx_idx] = 0.0
                else:
                    taper_pos = (v_app - v_taper_lo) / (v_thr - v_taper_lo)
                    mask[freq_idx, kx_idx] = 0.5 * (1.0 - np.cos(np.pi * taper_pos))

        filtered = np.real(np.fft.ifft2(fk * mask))

        denoised_traces: list[dict[str, Any]] = []
        for trace_idx, tr in enumerate(traces):
            sample_count = len(tr.get("samples", []))
            denoised_traces.append({**tr, "samples": filtered[:sample_count, trace_idx].tolist()})

        return {
            "denoised_traces": denoised_traces,
            "noise_model": {
                "velocity_threshold_m_s": float(velocity_threshold_m_s),
                "taper_width_pct": float(taper_width_pct),
            },
        }
