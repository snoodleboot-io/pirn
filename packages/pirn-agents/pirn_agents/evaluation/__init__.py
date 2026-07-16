"""Evaluation & quality harness (F12) — metrics, judge, runner, and CI gates.

A quality-evaluation harness distinct from F10's latency/throughput benchmarks:
it proves patterns are *correct*, not just fast. The subpackage layers four
capabilities, each provider-neutral and backend-free at import time:

* **Core metrics** — ``task_success``, ``exact_match``, ``semantic_match``: pure
  functions with no hard dependency on any specific LLM/embedding backend.
* **RAG metrics** — RAGAS-style faithfulness, context precision/recall, and
  answer relevance, each computed from a
  :class:`~pirn_agents.evaluation.rag_sample.RagSample` with a pluggable judge or
  embedding provider.
* **Trajectory metrics** — tool-choice accuracy, step efficiency, and
  redundant-call rate over a recorded agent
  :class:`~pirn_agents.evaluation.trajectory.Trajectory`.
* **LLM-as-judge** — :class:`~pirn_agents.evaluation.evaluation_judge.EvaluationJudge` with
  pairwise + rubric modes, position-swap and self-consistency bias controls, and
  gold-set calibration.
* **Datasets, runner, and gates** — an
  :class:`~pirn_agents.evaluation.eval_dataset.EvalDataset` format, the
  :func:`~pirn_agents.evaluation.run_eval.run_eval` runner, an
  :class:`~pirn_agents.evaluation.eval_report.EvalReport`, and an
  :class:`~pirn_agents.evaluation.eval_gate.EvalGate` for CI regression control.

Determinism (record/replay cassettes) is F29's job: the runner takes a
:class:`~pirn_agents.evaluation.run_recorder.RunRecorder` seam (defaulting to the
pass-through :class:`~pirn_agents.evaluation.null_run_recorder.NullRunRecorder`
over live I/O) that F29 will back with a cassette recorder.

Importing this subpackage pulls in no backend; the optional RAGAS/embedding-judge
backend is imported lazily through :func:`pirn_agents._require._require` behind
the flat ``ragas`` extra.
"""

from __future__ import annotations

__all__: list[str] = []
