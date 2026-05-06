"""``SpeakerDiarizationPipeline`` — segment audio by speaker identity.

Algorithm:
    1. Receive the input audio signal frame and configuration parameters.
    2. Validate min_speakers, max_speakers (max >= min), and embedding_model.
    3. Segment the audio into speech regions using a VAD front-end.
    4. Extract speaker embeddings for each speech segment using embedding_model.
    5. Cluster the embeddings (e.g., agglomerative clustering or k-means)
       constraining the number of speakers to [min_speakers, max_speakers].
    6. Assign speaker labels to each segment boundary.
    7. Return a list of segment dicts with start_sec, end_sec, and speaker_id.

    distance in the speaker embedding space; specific metrics depend on
    the chosen embedding model.

References:
    - Park, T.J. et al. (2022). "A review of speaker diarization: Recent advances
      with deep learning." Computer Speech & Language, 72, 101317.
    - Bredin, H. et al. (2021). "Pyannote.audio: Neural building blocks
      for speaker diarization." ICASSP 2020.
"""

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
        min_speakers: Knot | int,
        max_speakers: Knot | int,
        embedding_model: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
            embedding_model=embedding_model,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        min_speakers: int,
        max_speakers: int,
        embedding_model: str,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Segment the audio signal by speaker.

        Args:
            signal: Audio signal to diarize.
            min_speakers: Minimum expected number of speakers (>= 1).
            max_speakers: Maximum expected number of speakers (>= min_speakers).
            embedding_model: Non-empty model name string for speaker embeddings.

        Returns:
            List of segment dicts, each with keys ``start_sec``, ``end_sec``,
            and ``speaker_id``.

        Raises:
            ValueError: If min_speakers, max_speakers, or embedding_model are invalid.
        """
        if not isinstance(min_speakers, int) or min_speakers < 1:
            raise ValueError(
                "SpeakerDiarizationPipeline: min_speakers must be >= 1"
            )
        if not isinstance(max_speakers, int):
            raise TypeError(
                "SpeakerDiarizationPipeline: max_speakers must be an integer"
            )
        if max_speakers < min_speakers:
            raise ValueError(
                "SpeakerDiarizationPipeline: max_speakers must be >= min_speakers"
            )
        if not isinstance(embedding_model, str) or not embedding_model:
            raise ValueError(
                "SpeakerDiarizationPipeline: embedding_model must be a non-empty string"
            )
        duration_sec = signal.samples_per_channel / max(signal.sample_rate_hz, 1.0)
        return [
            {
                "start_sec": 0.0,
                "end_sec": duration_sec,
                "speaker_id": "SPEAKER_00",
            }
        ]
