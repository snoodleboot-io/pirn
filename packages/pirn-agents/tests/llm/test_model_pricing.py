"""Unit tests for :class:`pirn_agents.llm.model_pricing.ModelPricing`."""

from __future__ import annotations

import unittest

from pirn_agents.llm.model_pricing import ModelPricing


class TestModelPricing(unittest.TestCase):
    def test_zero_pricing_costs_nothing(self) -> None:
        pricing = ModelPricing()
        assert pricing.estimate_cost({"input_tokens": 100, "output_tokens": 50}) == 0.0

    def test_estimates_from_input_and_output(self) -> None:
        pricing = ModelPricing(input_per_million=1.0, output_per_million=2.0)
        # 1_000_000 input -> 1.0; 1_000_000 output -> 2.0
        cost = pricing.estimate_cost({"input_tokens": 1_000_000, "output_tokens": 1_000_000})
        assert cost == 3.0

    def test_cached_tokens_billed_at_cached_rate_and_deducted(self) -> None:
        pricing = ModelPricing(
            input_per_million=10.0, output_per_million=0.0, cached_input_per_million=1.0
        )
        # 1_000_000 input of which 400_000 cached:
        #   600_000 billable * 10 + 400_000 * 1 = 6_000_000 + 400_000 = 6_400_000 / 1e6
        cost = pricing.estimate_cost(
            {"input_tokens": 1_000_000, "cached_input_tokens": 400_000, "output_tokens": 0}
        )
        assert cost == 6.4

    def test_missing_fields_default_to_zero(self) -> None:
        pricing = ModelPricing(input_per_million=5.0, output_per_million=5.0)
        assert pricing.estimate_cost({}) == 0.0

    def test_audit_dict(self) -> None:
        pricing = ModelPricing(input_per_million=1.0)
        audit = pricing._pirn_audit_dict()
        assert audit["input_per_million"] == 1.0


if __name__ == "__main__":
    unittest.main()
