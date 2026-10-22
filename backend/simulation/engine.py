"""
WhatIf AI – Simulation Engine
==============================
All numerical work happens here. No LLM calls, no dynamic code execution.

Sections:
  1. Variable / distribution helpers
  2. Sensitivity Analysis
  3. Monte Carlo
  4. Scenario Comparison
  5. Cloud infrastructure domain model
  6. Top-level dispatcher
"""
from __future__ import annotations

import math
import time
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# Constants / version
# ---------------------------------------------------------------------------
ENGINE_VERSION = "1.0.0"
MAX_TRIALS = 100_000
SUPPORTED_DISTRIBUTIONS = {"normal", "uniform", "triangular", "lognormal", "fixed"}


# ---------------------------------------------------------------------------
# 1. Helpers
# ---------------------------------------------------------------------------

class SimulationError(Exception):
    """Raised when a simulation cannot be completed with the given inputs."""


def _draw_samples(var_def: dict, n: int, rng: np.random.Generator) -> np.ndarray:
    """
    Draw *n* samples from the distribution described by *var_def*.

    var_def keys:
        value     – central / default value (required)
        dist      – distribution name (default: 'fixed')
        std       – standard deviation (normal / lognormal)
        min, max  – bounds (uniform / triangular)
        mode      – mode (triangular)
    """
    dist = (var_def.get("dist") or "fixed").lower()
    v = float(var_def["value"])

    if dist == "fixed":
        return np.full(n, v)

    if dist == "normal":
        std = float(var_def.get("std", v * 0.1))
        samples = rng.normal(loc=v, scale=std, size=n)

    elif dist == "uniform":
        lo = float(var_def.get("min", v * 0.8))
        hi = float(var_def.get("max", v * 1.2))
        samples = rng.uniform(lo, hi, size=n)

    elif dist == "triangular":
        lo = float(var_def.get("min", v * 0.8))
        hi = float(var_def.get("max", v * 1.2))
        mode = float(var_def.get("mode", v))
        # scipy triangular parameterisation
        c = (mode - lo) / (hi - lo) if hi > lo else 0.5
        samples = stats.triang.rvs(c=c, loc=lo, scale=hi - lo, size=n, random_state=rng)

    elif dist == "lognormal":
        std = float(var_def.get("std", v * 0.1))
        sigma = math.sqrt(math.log(1 + (std / v) ** 2)) if v > 0 else 0.1
        mu = math.log(v) - sigma ** 2 / 2 if v > 0 else 0
        samples = rng.lognormal(mean=mu, sigma=sigma, size=n)

    else:
        raise SimulationError(f"Unknown distribution '{dist}'")

    # honour explicit bounds if given
    lo = var_def.get("min")
    hi = var_def.get("max")
    if lo is not None:
        samples = np.clip(samples, float(lo), None)
    if hi is not None:
        samples = np.clip(samples, None, float(hi))

    return samples


def _check_constraints(values: dict[str, float], constraints: list[dict]) -> list[str]:
    """Return a list of violated constraint descriptions."""
    violations: list[str] = []
    for c in constraints:
        name = c.get("name", "")
        op = c.get("operator", "<=")
        threshold = float(c.get("threshold", 0))
        actual = values.get(name)
        if actual is None:
            continue
        breached = {
            "<=": actual > threshold,
            ">=": actual < threshold,
            "<": actual >= threshold,
            ">": actual <= threshold,
            "==": actual != threshold,
        }.get(op, False)
        if breached:
            unit = c.get("unit", "")
            violations.append(
                f"{name} = {actual:.4g} {unit} violates {op} {threshold} {unit}"
            )
    return violations


# ---------------------------------------------------------------------------
# 2. Cloud Infrastructure Domain Model
# ---------------------------------------------------------------------------

def cloud_infra_cost(variables: dict[str, Any]) -> dict[str, float]:
    """
    Deterministic cloud infrastructure cost model.

    Variables (all float-valued):
        base_monthly_cost     – current monthly cloud spend ($)
        cost_increase_pct     – cost increase percentage (%)
        traffic_multiplier    – factor by which user traffic scales
        availability_target   – required uptime SLA (%)
        current_instances     – number of compute instances
        instance_cost_per_hr  – cost per instance per hour ($)
        storage_gb            – storage volume (GB)
        storage_cost_per_gb   – cost per GB per month ($)
        data_transfer_gb      – monthly data transfer (GB)
        transfer_cost_per_gb  – cost per GB transfer ($)
        redundancy_factor     – replication factor for HA (e.g. 2 for active-passive)

    Returns a dict of derived KPIs.

    Equations (documented):
        adjusted_cost = base_monthly_cost × (1 + cost_increase_pct/100)
        required_instances = ceil(current_instances × traffic_multiplier × redundancy_factor)
        compute_cost = required_instances × instance_cost_per_hr × 730   [hours/month]
        storage_cost = storage_gb × traffic_multiplier × storage_cost_per_gb
        transfer_cost = data_transfer_gb × traffic_multiplier × transfer_cost_per_gb
        total_monthly = adjusted_cost + compute_cost + storage_cost + transfer_cost
        annual_cost = total_monthly × 12
        cost_per_user_session = total_monthly / (traffic_multiplier × 10_000)  [assumed 10k sessions baseline]
        availability_overhead_pct = (redundancy_factor - 1) × 20  [approx overhead for HA]
    """
    v = {k: float(d["value"] if isinstance(d, dict) else d) for k, d in variables.items()}

    base = v.get("base_monthly_cost", 10_000)
    cost_inc_pct = v.get("cost_increase_pct", 0)
    traffic_mult = max(v.get("traffic_multiplier", 1.0), 0.01)
    availability_target = v.get("availability_target", 99.9)
    current_inst = max(v.get("current_instances", 4), 1)
    inst_hr = v.get("instance_cost_per_hr", 0.096)
    storage_gb = v.get("storage_gb", 500)
    storage_cost_gb = v.get("storage_cost_per_gb", 0.023)
    transfer_gb = v.get("data_transfer_gb", 1000)
    transfer_cost_gb = v.get("transfer_cost_per_gb", 0.09)

    # Redundancy: availability_target determines redundancy_factor
    # 99.9% → 2× (active-passive), 99.99% → 3× (multi-region)
    redundancy_factor = v.get("redundancy_factor", 1.0)
    if redundancy_factor <= 1.0:
        if availability_target >= 99.99:
            redundancy_factor = 3.0
        elif availability_target >= 99.9:
            redundancy_factor = 2.0
        else:
            redundancy_factor = 1.0

    adjusted_cost = base * (1 + cost_inc_pct / 100)
    required_instances = math.ceil(current_inst * traffic_mult * redundancy_factor)
    compute_cost = required_instances * inst_hr * 730
    storage_cost = storage_gb * traffic_mult * storage_cost_gb
    transfer_cost = transfer_gb * traffic_mult * transfer_cost_gb
    total_monthly = adjusted_cost + compute_cost + storage_cost + transfer_cost
    annual_cost = total_monthly * 12
    downtime_minutes_per_month = (1 - availability_target / 100) * 730 * 60
    availability_overhead_pct = (redundancy_factor - 1) * 20

    return {
        "adjusted_base_cost": round(adjusted_cost, 2),
        "required_instances": required_instances,
        "compute_cost": round(compute_cost, 2),
        "storage_cost": round(storage_cost, 2),
        "transfer_cost": round(transfer_cost, 2),
        "total_monthly_cost": round(total_monthly, 2),
        "annual_cost": round(annual_cost, 2),
        "downtime_minutes_per_month": round(downtime_minutes_per_month, 2),
        "availability_overhead_pct": round(availability_overhead_pct, 2),
        "redundancy_factor": redundancy_factor,
        "traffic_multiplier": traffic_mult,
        "cost_increase_pct": cost_inc_pct,
    }


DOMAIN_MODELS = {
    "cloud_infrastructure": cloud_infra_cost,
}


def _run_model(domain: str, variables: dict) -> dict[str, float]:
    fn = DOMAIN_MODELS.get(domain)
    if fn is None:
        raise SimulationError(f"Unknown domain '{domain}'")
    return fn(variables)


# ---------------------------------------------------------------------------
# 3. Sensitivity Analysis
# ---------------------------------------------------------------------------

def run_sensitivity_analysis(
    domain: str,
    variables: dict,
    constraints: list,
    perturbation_pct: float = 10.0,
    target_metric: str = "total_monthly_cost",
) -> dict:
    """
    One-at-a-time (OAT) sensitivity analysis.

    For each variable, perturb its value by ±perturbation_pct% while
    holding all others at their baseline values. Compute the elasticity
    (% change in target / % change in input) for each variable.

    Returns a dict suitable for frontend charting.
    """
    start = time.time()
    baseline_out = _run_model(domain, variables)
    baseline_val = baseline_out.get(target_metric, 0)
    if baseline_val == 0:
        raise SimulationError("Baseline target metric is zero; cannot compute elasticity.")

    sensitivities = []
    for var_name, var_def in variables.items():
        raw = var_def if isinstance(var_def, dict) else {"value": var_def}
        base_v = float(raw["value"])
        if base_v == 0:
            continue

        results_up = []
        results_down = []
        for pct in [perturbation_pct]:
            perturbed_up = dict(variables)
            perturbed_up[var_name] = {**raw, "value": base_v * (1 + pct / 100)}
            out_up = _run_model(domain, perturbed_up)
            results_up.append(out_up.get(target_metric, baseline_val))

            perturbed_down = dict(variables)
            perturbed_down[var_name] = {**raw, "value": base_v * (1 - pct / 100)}
            out_down = _run_model(domain, perturbed_down)
            results_down.append(out_down.get(target_metric, baseline_val))

        delta_up = (results_up[0] - baseline_val) / baseline_val * 100
        delta_down = (results_down[0] - baseline_val) / baseline_val * 100
        elasticity = delta_up / perturbation_pct if perturbation_pct else 0

        sensitivities.append({
            "variable": var_name,
            "baseline_value": base_v,
            "unit": raw.get("unit", ""),
            "delta_up_pct": round(delta_up, 3),
            "delta_down_pct": round(delta_down, 3),
            "elasticity": round(elasticity, 4),
            "abs_elasticity": round(abs(elasticity), 4),
        })

    sensitivities.sort(key=lambda x: x["abs_elasticity"], reverse=True)

    # Tornado chart data (±perturbation range)
    tornado = []
    for s in sensitivities:
        bv = s["baseline_value"]
        delta_up = baseline_val * (1 + s["delta_up_pct"] / 100)
        delta_down = baseline_val * (1 + s["delta_down_pct"] / 100)
        tornado.append({
            "variable": s["variable"],
            "low": round(min(delta_down, delta_up), 2),
            "high": round(max(delta_down, delta_up), 2),
            "baseline": round(baseline_val, 2),
        })

    elapsed = time.time() - start
    violations = _check_constraints(baseline_out, constraints)

    return {
        "method": "sensitivity",
        "target_metric": target_metric,
        "baseline": baseline_out,
        "perturbation_pct": perturbation_pct,
        "sensitivities": sensitivities,
        "tornado": tornado,
        "constraint_violations": violations,
        "elapsed_seconds": round(elapsed, 4),
        "engine_version": ENGINE_VERSION,
    }


# ---------------------------------------------------------------------------
# 4. Monte Carlo
# ---------------------------------------------------------------------------

def run_monte_carlo(
    domain: str,
    variables: dict,
    constraints: list,
    n_trials: int = 10_000,
    seed: int = 42,
    target_metrics: list[str] | None = None,
) -> dict:
    """
    Monte Carlo simulation.

    Draw n_trials samples from each variable's defined distribution,
    evaluate the domain model for each sample, and aggregate statistics.

    Uses a reproducible numpy default_rng(seed) generator.
    """
    if n_trials > MAX_TRIALS:
        raise SimulationError(f"n_trials {n_trials} exceeds maximum {MAX_TRIALS}")

    start = time.time()
    rng = np.random.default_rng(seed)

    if target_metrics is None:
        target_metrics = ["total_monthly_cost", "annual_cost", "required_instances"]

    # Draw samples matrix: var_name → array[n_trials]
    samples: dict[str, np.ndarray] = {}
    for var_name, var_def in variables.items():
        raw = var_def if isinstance(var_def, dict) else {"value": var_def}
        samples[var_name] = _draw_samples(raw, n_trials, rng)

    # Evaluate model for each trial
    metric_arrays: dict[str, list] = {m: [] for m in target_metrics}
    for i in range(n_trials):
        trial_vars = {
            k: {"value": float(samples[k][i]), **(variables[k] if isinstance(variables[k], dict) else {})}
            for k in variables
        }
        # Override the value drawn from the distribution
        for k in trial_vars:
            trial_vars[k] = {**trial_vars[k], "value": float(samples[k][i])}
        try:
            out = _run_model(domain, trial_vars)
            for m in target_metrics:
                metric_arrays[m].append(out.get(m, float("nan")))
        except Exception:
            for m in target_metrics:
                metric_arrays[m].append(float("nan"))

    # Aggregate statistics
    percentiles = [5, 10, 25, 50, 75, 90, 95]
    stats_out: dict[str, dict] = {}
    for m in target_metrics:
        arr = np.array(metric_arrays[m], dtype=float)
        valid = arr[~np.isnan(arr)]
        if len(valid) == 0:
            stats_out[m] = {"error": "all trials produced NaN"}
            continue
        pct_vals = np.percentile(valid, percentiles)
        stats_out[m] = {
            "mean": round(float(np.mean(valid)), 4),
            "std": round(float(np.std(valid)), 4),
            "min": round(float(np.min(valid)), 4),
            "max": round(float(np.max(valid)), 4),
            **{f"p{p}": round(float(pct_vals[i]), 4) for i, p in enumerate(percentiles)},
            "n_valid": int(len(valid)),
            "n_nan": int(n_trials - len(valid)),
        }

    # Constraint breach probabilities
    breach_probs: dict[str, float] = {}
    for c in constraints:
        cname = c.get("name", "")
        op = c.get("operator", "<=")
        threshold = float(c.get("threshold", 0))
        arr = np.array(metric_arrays.get(cname, []), dtype=float)
        if len(arr) == 0:
            continue
        valid = arr[~np.isnan(arr)]
        n = len(valid)
        if n == 0:
            continue
        breached = {
            "<=": np.sum(valid > threshold),
            ">=": np.sum(valid < threshold),
            "<": np.sum(valid >= threshold),
            ">": np.sum(valid <= threshold),
        }.get(op, 0)
        breach_probs[cname] = round(float(breached) / n, 4)

    # Histogram data for primary metric (first target)
    primary = target_metrics[0] if target_metrics else None
    histogram = {}
    if primary and primary in metric_arrays:
        arr = np.array(metric_arrays[primary], dtype=float)
        valid = arr[~np.isnan(arr)]
        if len(valid) > 0:
            hist_counts, hist_edges = np.histogram(valid, bins=40)
            histogram = {
                "counts": hist_counts.tolist(),
                "edges": [round(float(e), 2) for e in hist_edges],
            }

    elapsed = time.time() - start
    return {
        "method": "monte_carlo",
        "n_trials": n_trials,
        "seed": seed,
        "statistics": stats_out,
        "breach_probabilities": breach_probs,
        "histogram": histogram,
        "elapsed_seconds": round(elapsed, 4),
        "engine_version": ENGINE_VERSION,
    }


# ---------------------------------------------------------------------------
# 5. Scenario Comparison
# ---------------------------------------------------------------------------

def run_scenario_comparison(
    domain: str,
    scenarios: dict[str, dict],
    constraints: list,
) -> dict:
    """
    Compare multiple named scenarios (e.g. baseline, optimistic, pessimistic).

    Each entry in *scenarios* is a full variable dict.
    Returns a comparison table and chart-ready series data.
    """
    start = time.time()
    results: dict[str, dict] = {}
    for scenario_name, variables in scenarios.items():
        try:
            out = _run_model(domain, variables)
            violations = _check_constraints(out, constraints)
            results[scenario_name] = {**out, "constraint_violations": violations}
        except Exception as e:
            results[scenario_name] = {"error": str(e)}

    # Build chart series
    all_metrics = set()
    for r in results.values():
        all_metrics.update(k for k in r if k not in ("constraint_violations", "error"))

    series: dict[str, dict] = {}
    for metric in sorted(all_metrics):
        series[metric] = {
            name: results[name].get(metric)
            for name in results
        }

    elapsed = time.time() - start
    return {
        "method": "scenario_comparison",
        "scenarios": results,
        "series": series,
        "elapsed_seconds": round(elapsed, 4),
        "engine_version": ENGINE_VERSION,
    }


# ---------------------------------------------------------------------------
# 6. Dispatcher
# ---------------------------------------------------------------------------

def dispatch_simulation(
    method: str,
    domain: str,
    variables: dict,
    constraints: list,
    parameters: dict,
    seed: int = 42,
) -> dict:
    """
    Top-level entry point called by Django views.

    method: 'sensitivity' | 'monte_carlo' | 'scenario_comparison'
    """
    if method == "sensitivity":
        return run_sensitivity_analysis(
            domain=domain,
            variables=variables,
            constraints=constraints,
            perturbation_pct=float(parameters.get("perturbation_pct", 10.0)),
            target_metric=parameters.get("target_metric", "total_monthly_cost"),
        )
    elif method == "monte_carlo":
        return run_monte_carlo(
            domain=domain,
            variables=variables,
            constraints=constraints,
            n_trials=int(parameters.get("n_trials", 10_000)),
            seed=seed,
            target_metrics=parameters.get("target_metrics", ["total_monthly_cost", "annual_cost"]),
        )
    elif method == "scenario_comparison":
        scenarios = parameters.get("scenarios", {})
        if not scenarios:
            # auto-build baseline / optimistic / pessimistic
            scenarios = _auto_scenarios(variables)
        return run_scenario_comparison(
            domain=domain,
            scenarios=scenarios,
            constraints=constraints,
        )
    else:
        raise SimulationError(f"Unknown method '{method}'")


def _auto_scenarios(variables: dict) -> dict[str, dict]:
    """Build baseline/optimistic/pessimistic variants from a variable set."""
    def _adjust(variables: dict, factor: float) -> dict:
        out = {}
        for k, v in variables.items():
            raw = v if isinstance(v, dict) else {"value": v}
            out[k] = {**raw, "value": float(raw["value"]) * factor}
        return out

    return {
        "baseline": variables,
        "optimistic": _adjust(variables, 0.85),
        "pessimistic": _adjust(variables, 1.20),
    }
