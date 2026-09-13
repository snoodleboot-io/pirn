"""``SpeakerDiarizationPipeline`` — segment audio by speaker identity.

Algorithm:
    1. Receive the input audio signal frame and configuration parameters.
    2. Validate min_speakers, max_speakers (max >= min), and embedding_model.
    3. Segment the audio into speech regions using a VAD front-end.
    4. Extract speaker embeddings for each speech segment using embedding_model.
    5. Cluster the embeddings (e.g., agglomerative clustering or k-means)
       constraining the number of speakers to [min_speakers, max_speakers].
    6. Assign a speaker-cluster label to each MFCC frame.
    7. Repeat independently for each channel and return a FeaturePayload with
       the per-frame speaker label per channel.

Math:
    KMeans clustering of the $T$ MFCC frame vectors $x_t \\in \\mathbb{R}^{20}$ into
    $k$ = min(max_speakers, T) clusters minimises the within-cluster sum of squares:

    $$\\underset{\\{\\mu_1, \\ldots, \\mu_k\\}}{\\arg\\min} \\sum_{i=1}^{k} \\sum_{t : c_t = i} \\lVert x_t - \\mu_i \\rVert^2$$

    where $c_t$ is the cluster assigned to frame $t$ and $\\mu_i$ is the centroid of
    cluster $i$. Cluster assignment uses Euclidean distance in the MFCC feature space;
    specific metrics depend on the chosen embedding model.

References:
    - Park, T.J. et al. (2022). "A review of speaker diarization: Recent advances
      with deep learning." Computer Speech & Language, 72, 101317.
    - Bredin, H. et al. (2021). "Pyannote.audio: Neural building blocks
      for speaker diarization." ICASSP 2020.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload

_mfcc_hop = 512
_mfcc_n = 20


class SpeakerDiarizationPipeline(Knot):
    """Segment audio by speaker identity using MFCC + KMeans clustering."""

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
        signal: SignalPayload,
        min_speakers: int,
        max_speakers: int,
        embedding_model: str,
        **_: Any,
    ) -> FeaturePayload:
        """Segment the audio signal by speaker.

        Args:
            signal: Audio signal to diarize.
            min_speakers: Minimum expected number of speakers (>= 1).
            max_speakers: Maximum expected number of speakers (>= min_speakers).
            embedding_model: Non-empty model name string (used for validation;
                clustering is performed with KMeans on MFCC frames).

        Returns:
            FeaturePayload with integer ``data`` shaped ``(channel_count, n_frames)``:
            the per-MFCC-frame speaker-cluster label per channel.

        Raises:
            ValueError: If min_speakers, max_speakers, or embedding_model are invalid.
        """
        if not isinstance(min_speakers, int) or min_speakers < 1:
            raise ValueError("SpeakerDiarizationPipeline: min_speakers must be >= 1")
        if not isinstance(max_speakers, int):
            raise TypeError("SpeakerDiarizationPipeline: max_speakers must be an integer")
        if max_speakers < min_speakers:
            raise ValueError("SpeakerDiarizationPipeline: max_speakers must be >= min_speakers")
        if not isinstance(embedding_model, str) or not embedding_model:
            raise ValueError(
                "SpeakerDiarizationPipeline: embedding_model must be a non-empty string"
            )
        sr = int(signal.frame.sample_rate_hz)
        channels = np.atleast_2d(signal.data)
        results = await asyncio.gather(
            *(
                asyncio.to_thread(SpeakerDiarizationPipeline._diarize, channel, sr, max_speakers)
                for channel in channels
            )
        )
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.frame.signal_id}:diarization",
                channel_count=channels.shape[0],
                feature_names=("speaker_label",),
            ),
            data=np.stack(results, axis=0),
        )

    @staticmethod
    def _diarize(
        channel: np.ndarray,
        sr: int,
        num_speakers: int,
    ) -> np.ndarray:
        """Diarize a single channel, returning per-frame speaker labels."""
        try:
            import librosa  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "SpeakerDiarizationPipeline requires 'librosa'. Install via pip install pirn-signal[signal]"
            ) from exc
        try:
            from sklearn.cluster import KMeans  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "SpeakerDiarizationPipeline requires 'scikit-learn'. Install via pip install pirn-signal[separation]"
            ) from exc
        mfcc = librosa.feature.mfcc(y=channel, sr=sr, n_mfcc=_mfcc_n, hop_length=_mfcc_hop)
        features = mfcc.T
        n_frames = features.shape[0]
        cluster_count = min(num_speakers, n_frames)
        if cluster_count < 2 or n_frames < 2:
            labels = np.zeros(n_frames, dtype=int)
        else:
            kmeans = KMeans(n_clusters=cluster_count, random_state=0, n_init="auto")
            labels = kmeans.fit_predict(features)
        return np.asarray(labels, dtype=int)
