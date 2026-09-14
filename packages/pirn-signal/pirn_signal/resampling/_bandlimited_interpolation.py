"""``BandlimitedInterpolation`` — arbitrary-ratio resampling by windowed-sinc interpolation.

Private helper (not a Knot) behind :meth:`PolyResampling.resample_rate` for a rate
ratio that polyphase resampling cannot represent exactly with bounded integer
factors — e.g. a clock drift of a few parts per million, whose exact ratio
``44100 / 44100.37`` would need factors in the millions.

Algorithm:
    1. Output sample ``m`` sits at input position ``t_m = m * f_source / f_target``;
       produce ``ceil(N * f_target / f_source)`` outputs (the ``resample_poly`` count).
    2. The cutoff, relative to the input Nyquist frequency, is
       ``c = min(1, f_target / f_source)`` — below 1 when downsampling, so the kernel
       also anti-aliases.
    3. Each output is the sum of the input samples within ``half_width / c`` of
       ``t_m``, weighted by ``c sinc(c (t_m - k))`` times a Kaiser window over that
       support. Samples outside the signal count as zero (as in ``resample_poly``).
    4. Outputs are computed in blocks so memory stays bounded for long signals.

Math:
    $$y(m) = \\sum_{k} x(k)\\; c\\, \\operatorname{sinc}\\big(c\\,(t_m - k)\\big)\\;
      w\\!\\left(\\frac{c\\,(t_m - k)}{W}\\right), \\qquad t_m = m\\,\\frac{f_s}{f_t}$$

    with the Kaiser window

    $$w(u) = \\frac{I_0\\big(\\beta \\sqrt{1 - u^2}\\big)}{I_0(\\beta)}, \\quad |u| \\le 1$$

References:
    - Smith, J.O. (2002). "Digital Audio Resampling Home Page."
      https://ccrma.stanford.edu/~jos/resample/ (bandlimited interpolation).
    - Kaiser, J.F. (1974). "Nonrecursive digital filter design using the I0-sinh window
      function." Proc. IEEE ISCAS, 20-23.
    - Alternative: ``scipy.signal.resample`` (FFT) — exact ratio too, but assumes a
      periodic signal and wraps edge transients around; not chosen for that reason.
"""

from __future__ import annotations

import functools
import math
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray


class BandlimitedInterpolation:
    """Kaiser-windowed sinc interpolation at an exact, arbitrary rate ratio."""

    _half_width: ClassVar[int] = 32
    _kaiser_beta: ClassVar[float] = 10.0
    _block_size: ClassVar[int] = 16_384
    _table_resolution: ClassVar[int] = 1024

    @staticmethod
    def resample(
        data: NDArray[np.floating[Any]], source_rate_hz: float, target_rate_hz: float
    ) -> NDArray[np.floating[Any]]:
        """Resample ``data`` along its last axis from ``source_rate_hz`` to ``target_rate_hz``."""
        samples = np.asarray(data, dtype=float)
        input_length = samples.shape[-1]
        step = float(source_rate_hz) / float(target_rate_hz)
        output_length = math.ceil(input_length / step)
        cutoff = min(1.0, 1.0 / step)
        reach = int(math.ceil(BandlimitedInterpolation._half_width / cutoff))
        offsets = np.arange(-reach + 1, reach + 1)
        output = np.empty((*samples.shape[:-1], output_length), dtype=float)
        padded = np.concatenate(
            [samples, np.zeros((*samples.shape[:-1], 1), dtype=float)], axis=-1
        )
        for start in range(0, output_length, BandlimitedInterpolation._block_size):
            stop = min(output_length, start + BandlimitedInterpolation._block_size)
            positions = np.arange(start, stop, dtype=float) * step
            neighbours = np.floor(positions).astype(np.int64)[:, np.newaxis] + offsets
            distance = positions[:, np.newaxis] - neighbours
            weights = BandlimitedInterpolation._kernel(distance, cutoff)
            inside = (neighbours >= 0) & (neighbours < input_length)
            # Out-of-range neighbours read the appended zero sample.
            gathered = padded[..., np.where(inside, neighbours, input_length)]
            output[..., start:stop] = np.sum(gathered * weights, axis=-1)
        return output

    @staticmethod
    def _kernel(distance: NDArray[np.float64], cutoff: float) -> NDArray[np.float64]:
        """Kaiser-windowed, cutoff-scaled sinc at ``distance`` input samples.

        Read from :meth:`_kernel_table` by linear interpolation, as in Smith's
        bandlimited-interpolation implementation; the table's step of
        ``1 / _table_resolution`` zero crossings keeps the interpolation error below
        ``1e-6`` of the kernel peak.
        """
        table = BandlimitedInterpolation._kernel_table()
        position = np.abs(cutoff * distance) * BandlimitedInterpolation._table_resolution
        index = np.minimum(position.astype(np.int64), table.size - 2)
        fraction = position - index
        interpolated = table[index] * (1.0 - fraction) + table[index + 1] * fraction
        return cutoff * interpolated

    @staticmethod
    @functools.cache
    def _kernel_table() -> NDArray[np.float64]:
        """The windowed sinc sampled every ``1 / _table_resolution`` zero crossings (0 beyond)."""
        half_width = BandlimitedInterpolation._half_width
        points = np.arange(half_width * BandlimitedInterpolation._table_resolution + 2)
        scaled = points / BandlimitedInterpolation._table_resolution
        normalised = np.clip(scaled / half_width, 0.0, 1.0)
        beta = BandlimitedInterpolation._kaiser_beta
        window = np.i0(beta * np.sqrt(1.0 - normalised**2)) / np.i0(beta)
        return np.where(scaled <= half_width, np.sinc(scaled) * window, 0.0)
