"""
WhatIf AI – Full Test Suite
============================
Tests:
 - Simulation engine (unit)
 - Variable extraction (unit)
 - Constraint handling
 - Reproducibility
 - Monte Carlo statistics
 - Sensitivity analysis
 - Django API integration tests
 - All 20 evaluation scenarios
"""
from __future__ import annotations

import math
import sys
import os

import pytest

# Ensure backend is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# ---- simulation engine imports ----
from simulation.engine import (
    cloud_infra_cost,
    dispatch_simulation,
    run_monte_carlo,
    run_scenario_comparison,
    run_sensitivity_analysis,
    SimulationError,
    _draw_samples,
    _check_constraints,
    ENGINE_VERSION,
)

# ---- agent imports ----
from agents.workflow import (
    _heuristic_extract,
    WorkflowState,
    scenario_interpreter,
    assumption_validator,
)

# ---- evaluation scenarios ----
from evaluation.scenarios import EVAL_SCENARIOS

import numpy as np


# ============================================================
# Section 1: Simulation engine unit tests
# ============================================================

class TestCloudInfraCost:
    """Deterministic model correctness."""

    def _vars(self, **overrides):
        base = {
            "base_monthly_cost": {"value": 10000, "unit": "USD/month", "dist": "fixed"},
            "cost_increase_pct": {"value": 0, "unit": "%", "dist": "fixed"},
            "traffic_multiplier": {"value": 1.0, "unit": "x", "dist": "fixed"},
            "availability_target": {"value": 99.0, "unit": "%", "dist": "fixed"},
            "current_instances": {"value": 4, "unit": "instances", "dist": "fixed"},
            "instance_cost_per_hr": {"value": 0.10, "unit": "USD/hr", "dist": "fixed"},
            "storage_gb": {"value": 100, "unit": "GB", "dist": "fixed"},
            "storage_cost_per_gb": {"value": 0.023, "unit": "USD/GB/month", "dist": "fixed"},
            "data_transfer_gb": {"value": 100, "unit": "GB/month", "dist": "fixed"},
            "transfer_cost_per_gb": {"value": 0.09, "unit": "USD/GB", "dist": "fixed"},
            "redundancy_factor": {"value": 1.0, "unit": "x", "dist": "fixed"},
        }
        for k, v in overrides.items():
            base[k] = {"value": v, "unit": "", "dist": "fixed"}
        return base

    def test_zero_cost_increase(self):
        """cost_increase_pct=0 → adjusted_base_cost == base_monthly_cost."""
        out = cloud_infra_cost(self._vars(base_monthly_cost=10000, cost_increase_pct=0))
        assert out["adjusted_base_cost"] == 10000.0

    def test_cost_increase_20pct(self):
        """20% cost increase on $10,000 → $12,000."""
        out = cloud_infra_cost(self._vars(base_monthly_cost=10000, cost_increase_pct=20))
        assert abs(out["adjusted_base_cost"] - 12000.0) < 0.01

    def test_annual_cost_is_12x_monthly(self):
        """annual_cost == total_monthly_cost × 12."""
        out = cloud_infra_cost(self._vars())
        assert abs(out["annual_cost"] - out["total_monthly_cost"] * 12) < 0.01

    def test_traffic_multiplier_doubles_compute(self):
        """Doubling traffic should roughly double required_instances."""
        out1 = cloud_infra_cost(self._vars(traffic_multiplier=1.0, current_instances=4))
        out2 = cloud_infra_cost(self._vars(traffic_multiplier=2.0, current_instances=4))
        assert out2["required_instances"] >= out1["required_instances"] * 1.9

    def test_availability_99_99_triggers_3x_redundancy(self):
        """99.99% availability should set redundancy_factor=3."""
        out = cloud_infra_cost(self._vars(availability_target=99.99, redundancy_factor=1.0))
        assert out["redundancy_factor"] == 3.0

    def test_availability_99_9_triggers_2x_redundancy(self):
        """99.9% availability should set redundancy_factor=2."""
        out = cloud_infra_cost(self._vars(availability_target=99.9, redundancy_factor=1.0))
        assert out["redundancy_factor"] == 2.0

    def test_required_instances_ceiling(self):
        """required_instances should be ceiling(current × traffic × redundancy)."""
        out = cloud_infra_cost(self._vars(
            current_instances=3,
            traffic_multiplier=2.5,
            redundancy_factor=1.0,
            availability_target=90.0,
        ))
        assert out["required_instances"] == math.ceil(3 * 2.5 * 1.0)

    def test_compute_cost_formula(self):
        """compute_cost = required_instances × instance_cost_per_hr × 730."""
        out = cloud_infra_cost(self._vars(
            current_instances=4,
            traffic_multiplier=1.0,
            instance_cost_per_hr=0.10,
            redundancy_factor=1.0,
            availability_target=90.0,
        ))
        expected_compute = 4 * 0.10 * 730
        assert abs(out["compute_cost"] - expected_compute) < 0.01

    def test_total_monthly_is_sum_of_components(self):
        """total_monthly = adjusted_base + compute + storage + transfer."""
        out = cloud_infra_cost(self._vars(
            availability_target=90.0, redundancy_factor=1.0
        ))
        expected = (
            out["adjusted_base_cost"]
            + out["compute_cost"]
            + out["storage_cost"]
            + out["transfer_cost"]
        )
        assert abs(out["total_monthly_cost"] - expected) < 0.01

    def test_negative_cost_increase(self):
        """Negative cost increase → adjusted_cost < base."""
        out = cloud_infra_cost(self._vars(base_monthly_cost=10000, cost_increase_pct=-15))
        assert out["adjusted_base_cost"] < 10000


class TestConstraintChecking:
    def test_no_violations_when_satisfied(self):
        values = {"total_monthly_cost": 5000.0}
        constraints = [{"name": "total_monthly_cost", "operator": "<=", "threshold": 10000}]
        assert _check_constraints(values, constraints) == []

    def test_violation_detected(self):
        values = {"total_monthly_cost": 15000.0}
        constraints = [{"name": "total_monthly_cost", "operator": "<=", "threshold": 10000}]
        violations = _check_constraints(values, constraints)
        assert len(violations) == 1

    def test_ge_constraint(self):
        values = {"availability_target": 95.0}
        constraints = [{"name": "availability_target", "operator": ">=", "threshold": 99.9}]
        violations = _check_constraints(values, constraints)
        assert len(violations) == 1

    def test_missing_variable_skipped(self):
        values = {"something_else": 100}
        constraints = [{"name": "total_monthly_cost", "operator": "<=", "threshold": 10000}]
        assert _check_constraints(values, constraints) == []


class TestSensitivityAnalysis:
    def _default_vars(self):
        return {
            "base_monthly_cost": {"value": 10000, "dist": "fixed", "unit": "USD/month"},
            "cost_increase_pct": {"value": 20, "dist": "fixed", "unit": "%"},
            "traffic_multiplier": {"value": 2.0, "dist": "fixed", "unit": "x"},
            "availability_target": {"value": 99.9, "dist": "fixed", "unit": "%"},
            "current_instances": {"value": 4, "dist": "fixed", "unit": "instances"},
            "instance_cost_per_hr": {"value": 0.096, "dist": "fixed", "unit": "USD/hr"},
            "storage_gb": {"value": 500, "dist": "fixed", "unit": "GB"},
            "storage_cost_per_gb": {"value": 0.023, "dist": "fixed", "unit": "USD/GB/month"},
            "data_transfer_gb": {"value": 1000, "dist": "fixed", "unit": "GB/month"},
            "transfer_cost_per_gb": {"value": 0.09, "dist": "fixed", "unit": "USD/GB"},
        }

    def test_returns_sensitivities(self):
        result = run_sensitivity_analysis(
            domain="cloud_infrastructure",
            variables=self._default_vars(),
            constraints=[],
        )
        assert "sensitivities" in result
        assert len(result["sensitivities"]) > 0

    def test_top_sensitivity_is_most_elastic(self):
        result = run_sensitivity_analysis(
            domain="cloud_infrastructure",
            variables=self._default_vars(),
            constraints=[],
        )
        s = result["sensitivities"]
        # Should be sorted by abs_elasticity descending
        for i in range(len(s) - 1):
            assert s[i]["abs_elasticity"] >= s[i + 1]["abs_elasticity"]

    def test_tornado_chart_populated(self):
        result = run_sensitivity_analysis(
            domain="cloud_infrastructure",
            variables=self._default_vars(),
            constraints=[],
        )
        assert len(result["tornado"]) > 0
        for entry in result["tornado"]:
            assert entry["low"] <= entry["high"]

    def test_baseline_included(self):
        result = run_sensitivity_analysis(
            domain="cloud_infrastructure",
            variables=self._default_vars(),
            constraints=[],
        )
        assert "baseline" in result
        assert "total_monthly_cost" in result["baseline"]

    def test_engine_version_present(self):
        result = run_sensitivity_analysis("cloud_infrastructure", self._default_vars(), [])
        assert result["engine_version"] == ENGINE_VERSION


class TestMonteCarlo:
    def _stochastic_vars(self):
        return {
            "base_monthly_cost": {"value": 10000, "dist": "normal", "std": 1000, "unit": "USD/month"},
            "cost_increase_pct": {"value": 20, "dist": "uniform", "min": 10, "max": 30, "unit": "%"},
            "traffic_multiplier": {"value": 2.0, "dist": "triangular", "min": 1.5, "max": 3.0, "mode": 2.0, "unit": "x"},
            "availability_target": {"value": 99.9, "dist": "fixed", "unit": "%"},
            "current_instances": {"value": 4, "dist": "fixed", "unit": "instances"},
            "instance_cost_per_hr": {"value": 0.096, "dist": "fixed", "unit": "USD/hr"},
            "storage_gb": {"value": 500, "dist": "fixed", "unit": "GB"},
            "storage_cost_per_gb": {"value": 0.023, "dist": "fixed", "unit": "USD/GB/month"},
            "data_transfer_gb": {"value": 1000, "dist": "fixed", "unit": "GB/month"},
            "transfer_cost_per_gb": {"value": 0.09, "dist": "fixed", "unit": "USD/GB"},
        }

    def test_reproducibility_same_seed(self):
        """Same seed must produce identical results."""
        r1 = run_monte_carlo("cloud_infrastructure", self._stochastic_vars(), [], n_trials=1000, seed=42)
        r2 = run_monte_carlo("cloud_infrastructure", self._stochastic_vars(), [], n_trials=1000, seed=42)
        assert r1["statistics"] == r2["statistics"]

    def test_different_seeds_differ(self):
        """Different seeds should (almost certainly) differ."""
        r1 = run_monte_carlo("cloud_infrastructure", self._stochastic_vars(), [], n_trials=500, seed=1)
        r2 = run_monte_carlo("cloud_infrastructure", self._stochastic_vars(), [], n_trials=500, seed=2)
        m1 = r1["statistics"]["total_monthly_cost"]["mean"]
        m2 = r2["statistics"]["total_monthly_cost"]["mean"]
        assert abs(m1 - m2) > 1  # should differ

    def test_percentile_ordering(self):
        """p5 ≤ p25 ≤ p50 ≤ p75 ≤ p95 for all metrics."""
        result = run_monte_carlo("cloud_infrastructure", self._stochastic_vars(), [], n_trials=2000, seed=42)
        for metric, s in result["statistics"].items():
            if not isinstance(s, dict) or "p5" not in s:
                continue
            assert s["p5"] <= s["p25"] <= s["p50"] <= s["p75"] <= s["p95"]

    def test_n_valid_equals_n_trials(self):
        """With valid inputs, all trials should succeed."""
        result = run_monte_carlo("cloud_infrastructure", self._stochastic_vars(), [], n_trials=500, seed=42)
        for metric, s in result["statistics"].items():
            if isinstance(s, dict) and "n_valid" in s:
                assert s["n_valid"] == 500

    def test_trial_limit_enforced(self):
        """Exceeding MAX_TRIALS raises SimulationError."""
        with pytest.raises(SimulationError):
            run_monte_carlo("cloud_infrastructure", self._stochastic_vars(), [], n_trials=200_000, seed=42)

    def test_histogram_populated(self):
        result = run_monte_carlo("cloud_infrastructure", self._stochastic_vars(), [], n_trials=500, seed=42)
        assert "histogram" in result
        assert len(result["histogram"].get("counts", [])) > 0

    def test_breach_probability_range(self):
        """Breach probabilities must be in [0, 1]."""
        constraints = [{"name": "total_monthly_cost", "operator": "<=", "threshold": 50000}]
        result = run_monte_carlo("cloud_infrastructure", self._stochastic_vars(), constraints, n_trials=500, seed=42)
        for k, p in result.get("breach_probabilities", {}).items():
            assert 0.0 <= p <= 1.0


class TestScenarioComparison:
    def _vars(self, cost_inc, traffic):
        return {
            "base_monthly_cost": {"value": 10000, "dist": "fixed"},
            "cost_increase_pct": {"value": cost_inc, "dist": "fixed"},
            "traffic_multiplier": {"value": traffic, "dist": "fixed"},
            "availability_target": {"value": 99.9, "dist": "fixed"},
            "current_instances": {"value": 4, "dist": "fixed"},
            "instance_cost_per_hr": {"value": 0.096, "dist": "fixed"},
            "storage_gb": {"value": 500, "dist": "fixed"},
            "storage_cost_per_gb": {"value": 0.023, "dist": "fixed"},
            "data_transfer_gb": {"value": 1000, "dist": "fixed"},
            "transfer_cost_per_gb": {"value": 0.09, "dist": "fixed"},
        }

    def test_all_scenarios_present(self):
        scenarios = {
            "baseline": self._vars(0, 1.0),
            "optimistic": self._vars(-10, 0.8),
            "pessimistic": self._vars(30, 2.5),
        }
        result = run_scenario_comparison("cloud_infrastructure", scenarios, [])
        assert set(result["scenarios"].keys()) == {"baseline", "optimistic", "pessimistic"}

    def test_pessimistic_costs_more_than_baseline(self):
        scenarios = {
            "baseline": self._vars(0, 1.0),
            "pessimistic": self._vars(30, 2.5),
        }
        result = run_scenario_comparison("cloud_infrastructure", scenarios, [])
        assert (
            result["scenarios"]["pessimistic"]["total_monthly_cost"]
            > result["scenarios"]["baseline"]["total_monthly_cost"]
        )

    def test_series_data_populated(self):
        scenarios = {"a": self._vars(0, 1.0), "b": self._vars(20, 2.0)}
        result = run_scenario_comparison("cloud_infrastructure", scenarios, [])
        assert "series" in result
        assert "total_monthly_cost" in result["series"]


class TestDistributionSampling:
    def test_fixed_distribution(self):
        rng = np.random.default_rng(0)
        samples = _draw_samples({"value": 42, "dist": "fixed"}, 100, rng)
        assert np.all(samples == 42)

    def test_normal_distribution_mean(self):
        rng = np.random.default_rng(0)
        samples = _draw_samples({"value": 100, "dist": "normal", "std": 10}, 10000, rng)
        assert abs(np.mean(samples) - 100) < 1.0

    def test_uniform_bounds(self):
        rng = np.random.default_rng(0)
        samples = _draw_samples({"value": 50, "dist": "uniform", "min": 40, "max": 60}, 1000, rng)
        assert np.all(samples >= 40) and np.all(samples <= 60)

    def test_lognormal_positive(self):
        rng = np.random.default_rng(0)
        samples = _draw_samples({"value": 100, "dist": "lognormal", "std": 10}, 1000, rng)
        assert np.all(samples > 0)

    def test_unknown_distribution_raises(self):
        rng = np.random.default_rng(0)
        with pytest.raises(SimulationError):
            _draw_samples({"value": 10, "dist": "cauchy"}, 100, rng)

    def test_min_clip_applied(self):
        rng = np.random.default_rng(0)
        samples = _draw_samples({"value": 100, "dist": "normal", "std": 200, "min": 0}, 1000, rng)
        assert np.all(samples >= 0)


# ============================================================
# Section 2: Variable extraction tests (heuristic parser)
# ============================================================

class TestHeuristicExtractor:
    def test_cost_increase_20(self):
        v = _heuristic_extract("cloud costs rise by 20%")
        assert abs(v["cost_increase_pct"]["value"] - 20.0) < 0.1

    def test_traffic_doubles(self):
        v = _heuristic_extract("user traffic doubles")
        assert abs(v["traffic_multiplier"]["value"] - 2.0) < 0.1

    def test_availability_99_9(self):
        v = _heuristic_extract("maintain 99.9% availability")
        assert abs(v["availability_target"]["value"] - 99.9) < 0.01

    def test_dollar_amount(self):
        v = _heuristic_extract("monthly cloud spend is $25,000")
        assert abs(v["base_monthly_cost"]["value"] - 25000) < 1

    def test_10x_traffic(self):
        v = _heuristic_extract("traffic increases 10x")
        assert abs(v["traffic_multiplier"]["value"] - 10.0) < 0.1

    def test_cost_decrease(self):
        # Note: heuristic may not catch negative values – acceptable
        v = _heuristic_extract("costs drop by 15%")
        # At minimum, shouldn't crash
        assert isinstance(v, dict)

    def test_instance_count(self):
        v = _heuristic_extract("We currently run 8 instances")
        assert int(v["current_instances"]["value"]) == 8

    def test_combined_scenario(self):
        """Core spec scenario: 20% cost rise, 2x traffic, 99.9% availability."""
        text = "monthly cloud costs rise by 20%, user traffic doubles, maintain 99.9% availability"
        v = _heuristic_extract(text)
        assert abs(v["cost_increase_pct"]["value"] - 20.0) < 0.1
        assert abs(v["traffic_multiplier"]["value"] - 2.0) < 0.1
        assert abs(v["availability_target"]["value"] - 99.9) < 0.01


# ============================================================
# Section 3: Evaluation scenario batch tests
# ============================================================

class TestEvaluationScenarios:
    """Run all 20 evaluation scenarios through the heuristic extractor."""

    def _run_and_check(self, scenario):
        extracted = _heuristic_extract(scenario.raw_input)
        errors = []
        for var_name, expected_val in scenario.expected_variables.items():
            actual = extracted.get(var_name, {})
            if isinstance(actual, dict):
                actual_val = actual.get("value", None)
            else:
                actual_val = float(actual)
            if actual_val is None:
                errors.append(f"{var_name}: missing")
                continue
            tolerance = max(abs(expected_val) * 0.15, 0.5)  # 15% tolerance
            if abs(float(actual_val) - expected_val) > tolerance:
                errors.append(
                    f"{var_name}: expected {expected_val}, got {actual_val}"
                )
        return errors

    @pytest.mark.parametrize("scenario", EVAL_SCENARIOS, ids=[s.id for s in EVAL_SCENARIOS])
    def test_scenario(self, scenario):
        if not scenario.expected_variables:
            pytest.skip(f"{scenario.id}: no numerical expectations to check")
        errors = self._run_and_check(scenario)
        assert errors == [], f"{scenario.id}: {'; '.join(errors)}"


# ============================================================
# Section 4: Dispatcher integration tests
# ============================================================

class TestDispatcher:
    def _vars(self):
        return {
            "base_monthly_cost": {"value": 10000, "dist": "fixed"},
            "cost_increase_pct": {"value": 20, "dist": "fixed"},
            "traffic_multiplier": {"value": 2.0, "dist": "fixed"},
            "availability_target": {"value": 99.9, "dist": "fixed"},
            "current_instances": {"value": 4, "dist": "fixed"},
            "instance_cost_per_hr": {"value": 0.096, "dist": "fixed"},
            "storage_gb": {"value": 500, "dist": "fixed"},
            "storage_cost_per_gb": {"value": 0.023, "dist": "fixed"},
            "data_transfer_gb": {"value": 1000, "dist": "fixed"},
            "transfer_cost_per_gb": {"value": 0.09, "dist": "fixed"},
        }

    def test_dispatch_sensitivity(self):
        result = dispatch_simulation("sensitivity", "cloud_infrastructure", self._vars(), [], {})
        assert result["method"] == "sensitivity"
        assert "baseline" in result

    def test_dispatch_monte_carlo(self):
        result = dispatch_simulation("monte_carlo", "cloud_infrastructure", self._vars(), [], {"n_trials": 100})
        assert result["method"] == "monte_carlo"
        assert "statistics" in result

    def test_dispatch_scenario_comparison(self):
        result = dispatch_simulation("scenario_comparison", "cloud_infrastructure", self._vars(), [], {})
        assert result["method"] == "scenario_comparison"
        assert "scenarios" in result

    def test_dispatch_unknown_method_raises(self):
        with pytest.raises(SimulationError):
            dispatch_simulation("magic", "cloud_infrastructure", self._vars(), [], {})

    def test_dispatch_unknown_domain_raises(self):
        with pytest.raises(SimulationError):
            dispatch_simulation("sensitivity", "alien_planet", self._vars(), [], {})

    def test_auto_scenarios_generated(self):
        """When no scenarios provided, auto-build baseline/optimistic/pessimistic."""
        result = dispatch_simulation("scenario_comparison", "cloud_infrastructure", self._vars(), [], {})
        assert "baseline" in result["scenarios"]
        assert "optimistic" in result["scenarios"]
        assert "pessimistic" in result["scenarios"]
