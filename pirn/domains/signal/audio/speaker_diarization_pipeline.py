"""``SpeakerDiarizationPipeline`` — segment audio by speaker identity."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class SpeakerDiarizationPipeline(Knot):
    """Segment audio by speaker identity using speaker embeddings.

    Production needs ``pyannote.audio`` or a hand-rolled clustering
    pipeline.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        min_speakers: int,
        max_speakers: int,
        embedding_model: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(min_speakers, int) or min_speakers < 1:
            raise ValueError(
                "SpeakerDiarizationPipeline: min_speakers must be >= 1"
            )
        if not isinstance(max_speakers, int):
            raise TypeError(
                "SpeakerDiarizationPipeline: max_speakers must be an integer"
            )
        if not isinstance(embedding_model, str) or not embedding_model:
            raise ValueError(
                "SpeakerDiarizationPipeline: embedding_model must be a non-empty string"
            )
        self._min_speakers = min_speakers
        self._max_speakers = max_speakers
        self._embedding_model = embedding_model
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def min_speakers(self) -> int:
        return self._min_speakers

    @property
    def max_speakers(self) -> int:
        return self._max_speakers

    @property
    def embedding_model(self) -> str:
        return self._embedding_model

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> list[dict[str, Any]]:
        """Segment the audio signal by speaker and return a list of diarized segments.

        Args:
            signal: Audio signal to diarize.

        Returns:
            List of segment dicts, each with keys ``start_sec``, ``end_sec``,
            and ``speaker_id``.

        Raises:
            ValueError: If max_speakers is less than min_speakers.
        """
        if self._max_speakers < self._min_speakers:
            raise ValueError(
                "SpeakerDiarizationPipeline: max_speakers must be >= min_speakers"
            )
        duration_sec = signal.samples_per_channel / max(signal.sample_rate_hz, 1.0)
        return [
            {
                "start_sec": 0.0,
                "end_sec": duration_sec,
                "speaker_id": "SPEAKER_00",
            }
        ]
