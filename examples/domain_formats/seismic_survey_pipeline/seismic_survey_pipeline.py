"""Seismic survey analysis pipeline — static DAG over SEG-Y trace data.

Loads a set of synthetic SEG-Y traces, normalises amplitude and geometry,
then runs four independent analysers in parallel before assembling a survey
report.

Pipeline shape:

    TraceLoader ──► TraceNormaliser ──┬──► FrequencyAnalyser   ──┐
                                      ├──► AmplitudeScorer     ──┤
                                      ├──► VelocityEstimator   ──┼──► SurveyReport
                                      └──► HorizonPicker       ──┘

Working with real SEG-Y data:

    Replace ``SeismicSurveyPipeline.synthetic_traces()`` with bytes decoded by
    ``SegyFormat``:

        from pirn.connectors.file_formats.segy_format import SegyFormat

        fmt = SegyFormat(sample_rate=2000)
        traces = await fmt.decode(segy_bytes)   # one record per trace

    Each trace record has: trace_index (int), header (dict), data (float32 bytes).
    ``TraceLoader`` accepts that list directly.

Run with:
    uv run python -m examples.domain_formats.seismic_survey_pipeline
"""

from __future__ import annotations

import hashlib
import math
import random
import struct
from pathlib import Path
from typing import Any, ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from examples.domain_formats.seismic_survey_pipeline.amplitude_scorer import AmplitudeScorer
from examples.domain_formats.seismic_survey_pipeline.frequency_analyser import FrequencyAnalyser
from examples.domain_formats.seismic_survey_pipeline.horizon_picker import HorizonPicker
from examples.domain_formats.seismic_survey_pipeline.survey_report import SurveyReport
from examples.domain_formats.seismic_survey_pipeline.survey_result import SurveyResult
from examples.domain_formats.seismic_survey_pipeline.trace_loader import TraceLoader
from examples.domain_formats.seismic_survey_pipeline.trace_normaliser import TraceNormaliser
from examples.domain_formats.seismic_survey_pipeline.trace_record import TraceRecord
from examples.domain_formats.seismic_survey_pipeline.velocity_estimator import VelocityEstimator


class SeismicSurveyPipeline:
    """Builds and runs the seismic survey tapestry over a catalogue of surveys."""

    _surveys: ClassVar[tuple[str, ...]] = (
        "North-Sea-Block-42A",
        "Gulf-of-Mexico-GC-644",
        "Permian-Basin-3D-West",
    )

    @staticmethod
    def _rng(survey: str, extra: str = "") -> random.Random:
        """Return a deterministic RNG seeded from the survey name."""
        key = f"{survey}|{extra}"
        seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
        return random.Random(seed)

    @classmethod
    def synthetic_traces(
        cls, survey_name: str, n_traces: int = 120, n_samples: int = 500
    ) -> list[TraceRecord]:
        """Return synthetic trace records shaped like SegyFormat output."""
        rng = cls._rng(survey_name)
        records: list[TraceRecord] = []
        for i in range(n_traces):
            # Ricker wavelet with noise
            peak_t = rng.randint(80, 200)
            amplitude = rng.uniform(0.5, 2.0)
            values: list[float] = []
            for t in range(n_samples):
                dt = t - peak_t
                ricker = (
                    amplitude
                    * (1 - 2 * (math.pi * 30 * dt * 0.002) ** 2)
                    * math.exp(-((math.pi * 30 * dt * 0.002) ** 2))
                )
                noise = rng.gauss(0, 0.05 * amplitude)
                values.append(ricker + noise)
            data = struct.pack(f">{n_samples}f", *values)
            header: dict[str, Any] = {
                "CDP": i + 1,
                "OFFSET": rng.randint(100, 3000),
                "CDP_X": int(rng.uniform(400000, 400500) * 10),
                "CDP_Y": int(rng.uniform(6500000, 6500500) * 10),
                "DELRT": 0,
                "DT": 2000,
                "NS": n_samples,
            }
            records.append(TraceRecord(trace_index=i, header=header, data=data))
        return records

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire load → normalise → four parallel analysers → report."""
        with Tapestry(history=history) as t:
            survey_name = Parameter("survey_name", str, _config=KnotConfig(id="survey_name"))
            raw_traces = Parameter("traces", list, _config=KnotConfig(id="raw_traces"))

            loaded = TraceLoader(
                traces=raw_traces,
                survey_name=survey_name,
                _config=KnotConfig(id="loaded"),
            )
            normalised = TraceNormaliser(
                traces=loaded,
                _config=KnotConfig(id="normalised"),
            )
            freq = FrequencyAnalyser(
                survey=normalised,
                _config=KnotConfig(id="frequency"),
            )
            amp = AmplitudeScorer(
                survey=normalised,
                _config=KnotConfig(id="amplitude"),
            )
            vel = VelocityEstimator(
                survey=normalised,
                _config=KnotConfig(id="velocity"),
            )
            horizons = HorizonPicker(
                survey=normalised,
                _config=KnotConfig(id="horizons"),
            )
            SurveyReport(
                survey_name=survey_name,
                survey=normalised,
                frequency=freq,
                amplitude=amp,
                velocity=vel,
                horizons=horizons,
                _config=KnotConfig(id="report"),
            )
        return t

    @classmethod
    async def main(cls) -> None:
        """Run the pipeline once per survey and print each survey summary."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(history=history)

        print("\n── Seismic Survey Analysis Pipeline ──\n")

        for survey_name in cls._surveys:
            traces = cls.synthetic_traces(survey_name)
            req = RunRequest(
                parameters={
                    "survey_name": survey_name,
                    "traces": traces,
                }
            )
            r = await t.run(req)
            if not r.succeeded:
                exc = r.exceptions[0]
                print(f"  FAILED ({exc.knot_id}): {exc.message[:80]}")
                continue
            result: SurveyResult = r.outputs["report"]
            print(result.summary())
            print()
