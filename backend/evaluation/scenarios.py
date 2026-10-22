"""
WhatIf AI – Evaluation & Test Scenarios
========================================
20 labeled scenarios testing:
- Numerical extraction
- Missing assumption detection  
- Deterministic calculation correctness
- Reproducibility
- Sensitivity analysis
- Monte Carlo statistics
- Constraint handling
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalScenario:
    id: str
    description: str
    raw_input: str
    expected_variables: dict = field(default_factory=dict)   # var_name → approx value
    expected_violations: list = field(default_factory=list)  # expected constraint violations
    expect_clarification: bool = False
    domain: str = "cloud_infrastructure"
    notes: str = ""


EVAL_SCENARIOS: list[EvalScenario] = [
    EvalScenario(
        id="E01",
        description="Basic cost increase extraction",
        raw_input="What if monthly cloud costs rise by 20%?",
        expected_variables={"cost_increase_pct": 20.0},
        notes="Must extract 20 from '20%'",
    ),
    EvalScenario(
        id="E02",
        description="Traffic doubling extraction",
        raw_input="What if user traffic doubles?",
        expected_variables={"traffic_multiplier": 2.0},
        notes="Must interpret 'doubles' as ×2",
    ),
    EvalScenario(
        id="E03",
        description="Availability SLA extraction",
        raw_input="We need to maintain 99.9% availability.",
        expected_variables={"availability_target": 99.9},
    ),
    EvalScenario(
        id="E04",
        description="Combined multi-variable extraction",
        raw_input="What if monthly cloud costs rise by 20%, user traffic doubles, and we need to maintain 99.9% availability?",
        expected_variables={
            "cost_increase_pct": 20.0,
            "traffic_multiplier": 2.0,
            "availability_target": 99.9,
        },
        notes="Core scenario from spec",
    ),
    EvalScenario(
        id="E05",
        description="Explicit instance count",
        raw_input="We currently run 8 compute instances. What if traffic triples?",
        expected_variables={"current_instances": 8, "traffic_multiplier": 3.0},
    ),
    EvalScenario(
        id="E06",
        description="Explicit cost dollar amount",
        raw_input="Our monthly cloud spend is $25,000. What happens if it rises by 15%?",
        expected_variables={"base_monthly_cost": 25000, "cost_increase_pct": 15.0},
    ),
    EvalScenario(
        id="E07",
        description="High availability requiring 3× redundancy",
        raw_input="We need 99.99% uptime for our payment system.",
        expected_variables={"availability_target": 99.99},
        notes="Should trigger 3× redundancy_factor in model",
    ),
    EvalScenario(
        id="E08",
        description="No numeric values – should request clarification",
        raw_input="What if things get more expensive and we have more users?",
        expect_clarification=True,
        notes="Vague input – clarification should be requested",
    ),
    EvalScenario(
        id="E09",
        description="Boundary: 0% cost increase",
        raw_input="Assume costs stay flat. Traffic will double.",
        expected_variables={"cost_increase_pct": 0.0, "traffic_multiplier": 2.0},
    ),
    EvalScenario(
        id="E10",
        description="Large traffic multiplier",
        raw_input="What if we go viral and traffic increases 10x?",
        expected_variables={"traffic_multiplier": 10.0},
    ),
    EvalScenario(
        id="E11",
        description="Deterministic: base cost 10k, 0% increase, 1x traffic",
        raw_input="Current monthly cost is $10,000. No cost increase. Traffic stays the same.",
        expected_variables={"cost_increase_pct": 0.0, "traffic_multiplier": 1.0},
        notes="Total monthly cost should be deterministically calculable",
    ),
    EvalScenario(
        id="E12",
        description="Storage-heavy scenario",
        raw_input="We use 2TB of storage. What if data doubles and costs rise by 10%?",
        expected_variables={"storage_gb": 2000, "cost_increase_pct": 10.0, "traffic_multiplier": 2.0},
    ),
    EvalScenario(
        id="E13",
        description="Instance cost specification",
        raw_input="Each instance costs $0.20 per hour. We have 6 instances. Traffic will double.",
        expected_variables={
            "instance_cost_per_hr": 0.20,
            "current_instances": 6,
            "traffic_multiplier": 2.0,
        },
    ),
    EvalScenario(
        id="E14",
        description="Contradictory: 100% uptime (impossible)",
        raw_input="We need 100% uptime and will scale 5x.",
        expected_variables={"availability_target": 100.0, "traffic_multiplier": 5.0},
        expected_violations=["availability_target"],
        notes="100% uptime is unachievable; should flag or note impossibility",
    ),
    EvalScenario(
        id="E15",
        description="Cost reduction scenario",
        raw_input="What if we renegotiate and cloud costs drop by 15%?",
        expected_variables={"cost_increase_pct": -15.0},
        notes="Negative cost change",
    ),
    EvalScenario(
        id="E16",
        description="50% traffic reduction",
        raw_input="Traffic will drop by half after the campaign ends.",
        expected_variables={"traffic_multiplier": 0.5},
    ),
    EvalScenario(
        id="E17",
        description="Full explicit specification",
        raw_input=(
            "Base cost $15,000/month. Cost increase 25%. "
            "Traffic multiplier 3x. Availability 99.9%. "
            "12 instances at $0.15/hr. Storage 1000GB. Data transfer 2000GB."
        ),
        expected_variables={
            "base_monthly_cost": 15000,
            "cost_increase_pct": 25.0,
            "traffic_multiplier": 3.0,
            "availability_target": 99.9,
            "current_instances": 12,
            "instance_cost_per_hr": 0.15,
            "storage_gb": 1000,
            "data_transfer_gb": 2000,
        },
    ),
    EvalScenario(
        id="E18",
        description="Multiple constraints",
        raw_input="Costs must stay under $50,000/month. Traffic doubles. Availability 99.5%.",
        expected_variables={"traffic_multiplier": 2.0, "availability_target": 99.5},
        notes="Cost ceiling constraint",
    ),
    EvalScenario(
        id="E19",
        description="Probabilistic scenario for Monte Carlo",
        raw_input=(
            "Traffic is uncertain – could double or triple. "
            "Costs likely rise 15-25%. Need 99.9% availability."
        ),
        expected_variables={"availability_target": 99.9},
        notes="Should trigger Monte Carlo mode",
    ),
    EvalScenario(
        id="E20",
        description="Scenario comparison request",
        raw_input="Compare optimistic (10% cost rise, 1.5x traffic) vs pessimistic (40% cost rise, 3x traffic).",
        expected_variables={},
        notes="Should produce scenario_comparison result",
    ),
]
