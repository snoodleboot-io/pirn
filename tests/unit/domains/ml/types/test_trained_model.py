"""Tests for :class:`TrainedModel`."""

from __future__ import annotations

from datetime import datetime, timezone

from pirn.domains.ml.types.trained_model import TrainedModel


class TestTrainedModel:
    def test_construction_and_audit_dict(self) -> None:
        created_at = datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc)
        model = TrainedModel(
            model_id="rf:abc",
            algorithm="random_forest",
            hyperparameters={"n_estimators": 100},
            feature_names=("a", "b"),
            target_name="y",
            created_at=created_at,
        )
        audit = model._pirn_audit_dict()
        assert audit == {
            "model_id": "rf:abc",
            "algorithm": "random_forest",
            "hyperparameters": {"n_estimators": 100},
            "feature_names": ["a", "b"],
            "target_name": "y",
            "created_at": created_at.isoformat(),
        }
