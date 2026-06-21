"""``GreatExpectationsPandasValidator`` — bridge between a Great Expectations
:class:`ExpectationSuite` and pirn's :class:`QualityReport`.

Takes a Tier-2 :class:`PandasDataBatch` and validates it against a GE 1.x
``ExpectationSuite``. Validation runs through an
:class:`EphemeralDataContext` (in-memory, no project directory required),
so this knot is safe to use in tests and in pipelines that have no
on-disk GE configuration.

Failures are translated into one :class:`QualityCheck` per failed
expectation in ``result.results``, then bundled into a
:class:`QualityReport`. Same downstream shape as the rest of pirn's
quality knots — compose with :class:`pirn.nodes.gate.gate.Gate` keyed on
``QualityReport.passed`` to halt the pipeline on validation failure.

Why a parallel implementation rather than a sub-class of the Pandera
validator: GE's API is fundamentally different — suites are mutable
collections of declarative ``Expectation`` objects, validation goes
through a ``BatchDefinition``, and the result is a list of per-
expectation outcomes rather than a single ``failure_cases`` table. Each
framework owns its native vocabulary; pirn owns the orchestration.

Algorithm:
    1. Validate that ``suite`` is a ``great_expectations.ExpectationSuite``
       instance. Raise ``TypeError`` in ``process()`` if not.
    2. Build a fresh ephemeral ``EphemeralDataContext`` per execution so
       that parallel pipeline runs do not share registered data assets.
    3. Register the batch's Pandas DataFrame under a randomly suffixed data
       source, asset, and batch-definition name.
    4. Call ``ge_batch.validate(suite)`` and inspect ``result.success``.
    5. On success, emit a passing :class:`QualityReport` with no checks.
    6. On failure, translate each failing ``ExpectationValidationResult``
       into a :class:`QualityCheck` (one per expectation, not one per row).

    ```text
    ctx  = gx.get_context(mode="ephemeral")
    data = ctx.data_sources.add_pandas(unique_name).add_dataframe_asset(...)
    ge_batch = data.add_batch_definition_whole_dataframe(...).get_batch(...)
    result = ge_batch.validate(suite)
    if result.success:
        return QualityReport(passed=True)
    return QualityReport(passed=False, checks=failures_to_checks(result))
    ```

References:
    [1] Great Expectations — EphemeralDataContext and in-memory validation:
        https://docs.greatexpectations.io/docs/core/introduction/
    [2] Great Expectations — ExpectationSuite and BatchDefinition API (GE 1.x):
        https://docs.greatexpectations.io/docs/reference/api/
    [3] Alternative: Pandera (chosen GE here for declarative suite-based
        multi-column expectations; see PanderaPandasValidator for the
        Pandera counterpart):
        https://pandera.readthedocs.io/
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn_data.quality_check import QualityCheck
from pirn_data.quality_report import QualityReport


class GreatExpectationsPandasValidator(Knot):
    """Validate a :class:`PandasDataBatch` against a GE ``ExpectationSuite``."""

    def __init__(
        self,
        *,
        batch: Knot,
        suite: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, suite=suite, _config=_config, **kwargs)

    async def process(
        self,
        batch: PandasDataBatch,
        suite: Any,
        **_: Any,
    ) -> QualityReport:
        """Validate the PandasDataBatch against the GE ExpectationSuite and return a QualityReport.

        Args:
            batch: The PandasDataBatch to validate.
            suite: A ``great_expectations.ExpectationSuite`` instance.

        Returns:
            A QualityReport with one failed QualityCheck per failing expectation,
            or a passing report when all expectations are satisfied.
        """
        if not self._is_expectation_suite(suite):
            raise TypeError(
                "GreatExpectationsPandasValidator: suite must be a "
                "great_expectations.ExpectationSuite instance"
            )
        # Local import: keeps the module importable even when GE is not
        # installed. The type check above will already have raised TypeError
        # before this line runs in a real pipeline.
        import great_expectations as gx

        frame = batch.frame
        row_count = batch.row_count

        # Build a fresh ephemeral context per run so test isolation is
        # absolute and parallel pipeline runs don't trample each other's
        # registered assets. The cost is negligible for in-memory frames.
        context = gx.get_context(mode="ephemeral")
        # Names are random to keep ``add_pandas`` calls unique across
        # invocations should the underlying context ever be reused.
        suffix = uuid4().hex[:8]
        data_source = context.data_sources.add_pandas(f"pirn_pandas_{suffix}")
        asset = data_source.add_dataframe_asset(f"pirn_asset_{suffix}")
        batch_definition = asset.add_batch_definition_whole_dataframe(f"pirn_bd_{suffix}")
        ge_batch = batch_definition.get_batch(batch_parameters={"dataframe": frame})

        result = ge_batch.validate(suite)

        if result.success:
            return QualityReport(
                passed=True,
                checks=(),
                row_count=row_count,
            )
        return QualityReport(
            passed=False,
            checks=self._failures_to_checks(result),
            row_count=row_count,
        )

    @staticmethod
    def _is_expectation_suite(candidate: Any) -> bool:
        """Recognise a ``gx.ExpectationSuite`` without hard-importing GE.

        Returns ``False`` when GE isn't installed so the construction
        path raises a clean ``TypeError`` rather than ``ImportError``.
        """
        try:
            import great_expectations as gx
        except ImportError:
            return False
        return isinstance(candidate, gx.ExpectationSuite)

    @staticmethod
    def _failures_to_checks(result: Any) -> tuple[QualityCheck, ...]:
        """Translate per-expectation failures into pirn ``QualityCheck`` rows.

        ``result.results`` is a list of ``ExpectationValidationResult``
        objects, each with ``.success``, ``.expectation_config`` (with
        ``.type`` and ``.kwargs``), and ``.result`` (a dict containing
        ``unexpected_count``, ``partial_unexpected_list``, etc., depending
        on the expectation kind).
        """
        checks: list[QualityCheck] = []
        for outcome in getattr(result, "results", []) or []:
            if outcome.success:
                continue
            config = getattr(outcome, "expectation_config", None)
            kwargs: dict[str, Any] = {}
            name = "great_expectations_check"
            column: str | None = None
            if config is not None:
                kwargs = dict(getattr(config, "kwargs", {}) or {})
                name = getattr(config, "type", name)
                col_value = kwargs.get("column")
                column = str(col_value) if col_value is not None else None

            checks.append(
                QualityCheck(
                    name=str(name),
                    passed=False,
                    threshold=GreatExpectationsPandasValidator._serialise_threshold(kwargs),
                    actual=GreatExpectationsPandasValidator._serialise_actual(
                        getattr(outcome, "result", None)
                    ),
                    column=column,
                )
            )
        return tuple(checks)

    @staticmethod
    def _serialise_threshold(kwargs: dict[str, Any]) -> str:
        """Render the expectation's parameters (sans ``column``) as JSON.

        Falls back to ``str(...)`` if a value isn't JSON-serialisable so
        the audit log never loses information just because GE handed us
        something exotic (e.g. a numpy scalar).
        """
        rendered = {k: v for k, v in kwargs.items() if k != "column"}
        try:
            return json.dumps(rendered, default=str, sort_keys=True)
        except (TypeError, ValueError):
            return str(rendered)

    @staticmethod
    def _serialise_actual(result_dict: Any) -> str:
        """Summarise the failing data sample.

        GE's ``result`` dict carries different keys per expectation. We
        reach for the most informative one available; if none is present,
        we serialise the whole dict for full audit trail.
        """
        if not result_dict:
            return ""
        if not isinstance(result_dict, dict):
            return str(result_dict)
        for key in (
            "partial_unexpected_list",
            "unexpected_list",
            "observed_value",
            "unexpected_count",
        ):
            if key in result_dict:
                value = result_dict[key]
                try:
                    return json.dumps(value, default=str)
                except (TypeError, ValueError):
                    return str(value)
        try:
            return json.dumps(result_dict, default=str, sort_keys=True)
        except (TypeError, ValueError):
            return str(result_dict)
