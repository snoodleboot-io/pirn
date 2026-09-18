"""``MneSampleArrayDecoder`` — decode the bytes an MNE signal disassembler wrote.

:class:`~pirn_health.disassemblers.mne_signal_object_store_disassembler.MneSignalObjectStoreDisassembler`
serialises ``HealthSignalPayload.data`` with ``np.save``, i.e. a single NumPy
``.npy`` buffer. The EEG and MEG assemblers are the other half of that round
trip, so they decode ``.npy`` here. A ``.npz`` archive (what an external
producer may upload) is accepted too and must hold exactly one array, since
which of several arrays carried the samples would otherwise be a guess.

Bytes that do not decode, or an array whose shape contradicts the declared
frame metadata, raise: a recording that failed to load is not a recording of
silence, and returning zeros of the declared shape would hand downstream knots
a signal that passes every validation while carrying no data.

Algorithm:
    1. Load the buffer with ``np.load`` (``allow_pickle=False``).
    2. Take the single array (``.npy``) or the archive's only member (``.npz``).
    3. Promote a 1-D array to a single-channel 2-D array.
    4. Require the result to be 2-D of the declared ``(channel_count, samples)``.

References:
    - numpy.lib.format (the ``.npy``/``.npz`` layout):
      https://numpy.org/doc/stable/reference/generated/numpy.lib.format.html
"""

from __future__ import annotations

import io

import numpy as np
from numpy.typing import NDArray


class MneSampleArrayDecoder:
    """Decode object-store bytes into a validated ``(channel_count, samples)`` array."""

    @staticmethod
    def decode(
        body: bytes,
        *,
        knot_name: str,
        channel_count: int,
        samples_per_channel: int,
    ) -> NDArray[np.float32]:
        """Decode ``body`` and check it against the declared frame geometry.

        Args:
            body: Raw object-store bytes in NumPy ``.npy`` or single-array ``.npz`` format.
            knot_name: Name of the calling knot, used to prefix error messages.
            channel_count: Declared number of channels.
            samples_per_channel: Declared number of samples per channel.

        Returns:
            The decoded sample array, shape ``(channel_count, samples_per_channel)``.

        Raises:
            ValueError: If the bytes do not decode, the archive does not hold exactly
                one array, or the array's shape contradicts the declared geometry.
        """
        data = MneSampleArrayDecoder._load(body, knot_name)
        if data.ndim == 1:
            data = data[np.newaxis, :]
        expected = (channel_count, samples_per_channel)
        if data.shape != expected:
            raise ValueError(
                f"{knot_name}: decoded sample array has shape {data.shape}, but the "
                f"declared frame is {expected} — the stored object does not match the "
                f"metadata it was fetched with"
            )
        return data

    @staticmethod
    def _load(body: bytes, knot_name: str) -> NDArray[np.float32]:
        """Return the one array in ``body`` as float32, raising ValueError otherwise.

        ``np.load`` returns an array for a ``.npy`` buffer and an ``NpzFile`` — whose
        ``files`` lists its members — for a ``.npz`` archive; both are typed ``Any`` by
        the NumPy stubs, so the member is converted through ``np.asarray`` rather than
        narrowed by ``isinstance``.
        """
        try:
            loaded = np.load(io.BytesIO(body), allow_pickle=False)
        except Exception as exc:
            raise ValueError(
                f"{knot_name}: object body is not a NumPy .npy/.npz buffer ({exc})"
            ) from exc
        if hasattr(loaded, "files"):
            names = [str(name) for name in loaded.files]
            if len(names) != 1:
                raise ValueError(
                    f"{knot_name}: .npz archive must hold exactly one array, got {names}"
                )
            return np.asarray(loaded[names[0]], dtype=np.float32)
        return np.asarray(loaded, dtype=np.float32)
