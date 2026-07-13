"""Mirrored tests for :class:`RetrySafetyClassifier` (PIR-506 / S5)."""

from __future__ import annotations

import pytest

from pirn_agents.resilience.retry_classification import RetryClassification
from pirn_agents.resilience.retry_safety_classifier import RetrySafetyClassifier


class _HttpError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"http {status_code}")
        self.status_code = status_code


class TestExceptionTypes:
    @pytest.mark.parametrize(
        "error",
        [TimeoutError("t"), ConnectionError("c"), OSError("o")],
    )
    def test_transient_exceptions_are_safe(self, error: BaseException) -> None:
        assert RetrySafetyClassifier().classify(error) is RetryClassification.SAFE

    def test_validation_error_is_unsafe(self) -> None:
        assert RetrySafetyClassifier().classify(ValueError("bad")) is RetryClassification.UNSAFE

    def test_unknown_defaults_unsafe(self) -> None:
        assert RetrySafetyClassifier().classify(RuntimeError("?")) is RetryClassification.UNSAFE


class TestStatusCodes:
    @pytest.mark.parametrize("code", [429, 408, 425, 500, 502, 503, 504])
    def test_transient_status_codes_are_safe(self, code: int) -> None:
        assert RetrySafetyClassifier().is_safe(_HttpError(code)) is True

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 409, 422])
    def test_client_status_codes_are_unsafe(self, code: int) -> None:
        assert RetrySafetyClassifier().is_safe(_HttpError(code)) is False

    def test_status_code_precedes_exception_type(self) -> None:
        # An OSError subclass would be "safe" by type, but a 400 status forces unsafe.
        class _Weird(OSError):
            status_code = 400

        assert RetrySafetyClassifier().classify(_Weird()) is RetryClassification.UNSAFE


class TestConfiguration:
    def test_custom_safe_exceptions(self) -> None:
        classifier = RetrySafetyClassifier(safe_exceptions=(KeyError,))
        assert classifier.is_safe(KeyError("k")) is True
        # TimeoutError is no longer in the safe set.
        assert classifier.is_safe(TimeoutError()) is False

    def test_rejects_non_exception_type(self) -> None:
        with pytest.raises(TypeError, match="exception types"):
            RetrySafetyClassifier(safe_exceptions=(int,))  # type: ignore[arg-type]
