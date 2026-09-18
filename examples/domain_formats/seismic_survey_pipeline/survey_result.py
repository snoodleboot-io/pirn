"""``SurveyResult`` — every analyser's output for one survey, plus its summary.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass

from examples.domain_formats.seismic_survey_pipeline.amplitude_stats import AmplitudeStats
from examples.domain_formats.seismic_survey_pipeline.frequency_spectrum import FrequencySpectrum
from examples.domain_formats.seismic_survey_pipeline.horizon_pick import HorizonPick
from examples.domain_formats.seismic_survey_pipeline.velocity_model import VelocityModel


@dataclass
class SurveyResult:
    survey_name: str
    n_traces: int
    frequency: FrequencySpectrum
    amplitude: AmplitudeStats
    velocity: VelocityModel
    horizons: list[HorizonPick]

    def summary(self) -> str:
        hz = f"{self.frequency.dominant_hz:.0f} Hz"
        snr = f"{self.frequency.signal_to_noise:.1f} dB"
        rms = f"{self.amplitude.rms_amplitude:.3f}"
        hrz = "  ".join(
            f"{h.name}@{h.two_way_time_ms:.0f}ms({h.confidence:.0%})" for h in self.horizons
        )
        return (
            f"[{self.survey_name}] {self.n_traces} traces\n"
            f"  Frequency : {hz} dominant · SNR {snr}\n"
            f"  Amplitude : RMS={rms} · "
            f"dynamic range {self.amplitude.dynamic_range_db:.0f} dB\n"
            f"  Velocity  : Vrms(target)={self.velocity.vrms_target:.0f} m/s · "
            f"TWT={self.velocity.two_way_time_ms:.0f} ms\n"
            f"  Horizons  : {hrz}"
        )
