"""``SpeakerDiarizationPipeline`` — segment audio by speaker identity.

Algorithm:
    1. Receive the input audio signal frame and the speaker-count bounds.
    2. Validate min_speakers and max_speakers (max >= min).
    3. Extract per-frame MFCC vectors — the speaker features this pipeline
       clusters; it runs no neural embedding model and no VAD front-end.
    4. Cluster the frames with k-means for every candidate speaker count in
       [min_speakers, max_speakers] and keep the clustering with the highest
       silhouette coefficient, so the number of speakers is chosen inside the
       requested bounds rather than fixed at the maximum.
    5. Repeat independently for each channel and return a FeaturePayload with
       the per-frame speaker label per channel.

Math:
    KMeans clustering of the $T$ MFCC frame vectors $x_t \\in \\mathbb{R}^{20}$ into
    $k$ = min(max_speakers, T) clusters minimises the within-cluster sum of squares:

    $$\\underset{\\{\\mu_1, \\ldots, \\mu_k\\}}{\\arg\\min} \\sum_{i=1}^{k} \\sum_{t : c_t = i} \\lVert x_t - \\mu_i \\rVert^2$$

    where $c_t$ is the cluster assigned to frame $t$ and $\\mu_i$ is the centroid of
    cluster $i$. Cluster assignment uses Euclidean distance in the MFCC feature space.

    The speaker count is chosen by the mean silhouette coefficient over the
    candidates $k \\in [\\text{min\\_speakers}, \\text{max\\_speakers}]$:

    $$s(t) = \\frac{b(t) - a(t)}{\\max(a(t),\\, b(t))}$$

    with $a(t)$ the mean distance from frame $t$ to its own cluster and $b(t)$ the
    mean distance to the nearest other cluster.

References:
    - Park, T.J. et al. (2022). "A review of speaker diarization: Recent advances
      with deep learning." Computer Speech & Language, 72, 101317.
    - Bredin, H. et al. (2021). "Pyannote.audio: Neural building blocks
      for speaker diarization." ICASSP 2020.
    - Rousseeuw, P.J. (1987). "Silhouettes: a graphical aid to the interpretation and
      validation of cluster analysis." J. Comput. Appl. Math., 20, 53-65.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.optional_dependency import OptionalDependency

from pirn_signal.bindings.sklearn_cluster_binding import SklearnClusterBinding
from pirn_signal.bindings.sklearn_metrics_binding import SklearnMetricsBinding
from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


class SpeakerDiarizationPipeline(Knot):
    """Segment audio by speaker identity using MFCC + KMeans clustering."""

    _mfcc_hop: ClassVar[int] = 512
    _mfcc_n: ClassVar[int] = 20

    def __init__(
        self,
        *,
        signal: Knot,
        min_speakers: Knot | int,
        max_speakers: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        min_speakers: int,
        max_speakers: int,
        **_: Any,
    ) -> FeaturePayload:
        """Segment the audio signal by speaker.

        Args:
            signal: Audio signal to diarize.
            min_speakers: Minimum number of speakers to consider (>= 1).
            max_speakers: Maximum number of speakers to consider (>= min_speakers).

        Returns:
            FeaturePayload with integer ``data`` shaped ``(channel_count, n_frames)``:
            the per-MFCC-frame speaker-cluster label per channel.

        Raises:
            TypeError: If max_speakers is not an integer.
            ValueError: If min_speakers or max_speakers are invalid.
        """
        if not isinstance(min_speakers, int) or min_speakers < 1:
            raise ValueError("SpeakerDiarizationPipeline: min_speakers must be >= 1")
        if not isinstance(max_speakers, int):
            raise TypeError("SpeakerDiarizationPipeline: max_speakers must be an integer")
        if max_speakers < min_speakers:
            raise ValueError("SpeakerDiarizationPipeline: max_speakers must be >= min_speakers")
        sr = int(signal.metadata.sample_rate_hz)
        channels = np.atleast_2d(signal.data)
        results = await asyncio.gather(
            *(
                asyncio.to_thread(
                    SpeakerDiarizationPipeline._diarize,
                    channel,
                    sr,
                    min_speakers,
                    max_speakers,
                )
                for channel in channels
            )
        )
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.metadata.signal_id}:diarization",
                channel_count=channels.shape[0],
                feature_names=("speaker_label",),
            ),
            data=np.stack(results, axis=0),
        )

    @staticmethod
    def _diarize(
        channel: np.ndarray,
        sr: int,
        min_speakers: int,
        max_speakers: int,
    ) -> np.ndarray:
        """Diarize a single channel, returning per-frame speaker labels.

        The speaker count is selected inside ``[min_speakers, max_speakers]`` by
        silhouette coefficient, so a two-speaker recording analysed with
        ``max_speakers=8`` is not split into eight speakers.
        """
        librosa = OptionalDependency.require("librosa", extra="signal", package="pirn-signal")
        mfcc = librosa.feature.mfcc(
            y=channel,
            sr=sr,
            n_mfcc=SpeakerDiarizationPipeline._mfcc_n,
            hop_length=SpeakerDiarizationPipeline._mfcc_hop,
        )
        return SpeakerDiarizationPipeline._best_labels(mfcc.T, min_speakers, max_speakers)

    @staticmethod
    def _best_labels(
        features: NDArray[np.floating[Any]], min_speakers: int, max_speakers: int
    ) -> NDArray[np.int_]:
        """Highest-silhouette k-means labelling over the allowed speaker counts.

        Args:
            features: One MFCC vector per frame, shaped ``(n_frames, n_mfcc)``.
            min_speakers: Smallest speaker count to consider.
            max_speakers: Largest speaker count to consider.

        Returns:
            The per-frame speaker label of the best-scoring clustering; a single
            all-zero label array when the channel has too few frames to cluster.
        """
        frame_count = features.shape[0]
        upper = min(max_speakers, frame_count - 1)
        if frame_count < 2 or upper < max(2, min_speakers):
            return np.zeros(frame_count, dtype=np.int_)
        cluster = SklearnClusterBinding.load()
        metrics = SklearnMetricsBinding.load()
        best_labels = np.zeros(frame_count, dtype=np.int_)
        best_score = -2.0
        for cluster_count in range(max(2, min_speakers), upper + 1):
            labels = cluster.kmeans_labels(features, cluster_count)
            if len(np.unique(labels)) < 2:
                continue
            score = metrics.silhouette(features, labels)
            if score > best_score:
                best_score, best_labels = score, labels
        return best_labels
