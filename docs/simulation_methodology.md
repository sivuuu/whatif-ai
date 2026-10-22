# WhatIf AI — Simulation Methodology

## Disclaimer

All models use documented equations with user-supplied or default values.
The system never claims to represent an actual production environment,
and all cost rates used as defaults are illustrative only.
Users MUST validate all inputs against their actual infrastructure data.

---

## Domain: Cloud Infrastructure (`cloud_infrastructure`)

### Variables

| Variable | Default | Unit | Description |
|---|---|---|---|
| `base_monthly_cost` | 10,000 | USD/month | Current cloud spend |
| `cost_increase_pct` | 0 | % | Cost increase over baseline |
| `traffic_multiplier` | 1.0 | × | Scale factor for user traffic |
| `availability_target` | 99.9 | % | Required SLA uptime |
| `current_instances` | 4 | instances | Current compute instances |
| `instance_cost_per_hr` | 0.096 | USD/hr | Cost per instance per hour |
| `storage_gb` | 500 | GB | Storage volume |
| `storage_cost_per_gb` | 0.023 | USD/GB/month | Storage unit cost |
| `data_transfer_gb` | 1,000 | GB/month | Outbound data transfer |
| `transfer_cost_per_gb` | 0.09 | USD/GB | Transfer unit cost |

### Equations

```
# Adjusted base cost
adjusted_base_cost = base_monthly_cost × (1 + cost_increase_pct / 100)

# Redundancy factor (derived from availability_target)
if availability_target >= 99.99: redundancy_factor = 3.0
elif availability_target >= 99.9: redundancy_factor = 2.0
else: redundancy_factor = 1.0

# Compute scaling
required_instances = ceil(current_instances × traffic_multiplier × redundancy_factor)
compute_cost = required_instances × instance_cost_per_hr × 730    # 730 hours/month

# Storage (scales with traffic)
storage_cost = storage_gb × traffic_multiplier × storage_cost_per_gb

# Data transfer (scales with traffic)
transfer_cost = data_transfer_gb × traffic_multiplier × transfer_cost_per_gb

# Totals
total_monthly_cost = adjusted_base_cost + compute_cost + storage_cost + transfer_cost
annual_cost = total_monthly_cost × 12

# Downtime
downtime_minutes_per_month = (1 - availability_target / 100) × 730 × 60
```

### Assumptions

1. **Hours per month**: 730 (= 24 × 365 / 12)
2. **Redundancy**: 99.9% SLA → active-passive (2×); 99.99% → multi-region (3×)
3. **Storage scales linearly** with traffic multiplier (conservative assumption)
4. **Data transfer scales linearly** with traffic multiplier
5. **No volume discounts** are modelled

---

## Simulation Modes

### A. Sensitivity Analysis (OAT)

One-at-a-time (OAT) perturbation.

```
For each variable v_i:
  perturb up:   set v_i = v_i × (1 + Δ/100), hold others constant
  perturb down: set v_i = v_i × (1 - Δ/100), hold others constant
  
  elasticity_i = (Δ_output_pct / Δ_input_pct)
                = ((f(v_i_up) - f_base) / f_base) / (Δ/100)
```

Default Δ = 10%. Variables sorted by |elasticity|.
Tornado chart shows the [f(v_i_down), f(v_i_up)] range for each variable.

### B. Monte Carlo Simulation

```
seed = user-specified (default 42)
rng = numpy.random.default_rng(seed)

For trial t = 1 … N:
  For each variable v_i:
    sample x_i ~ Distribution(v_i.params, rng)
  output_t = model(x_1, …, x_n)

Statistics:
  mean, std, min, max, p5, p10, p25, p50, p75, p90, p95
  
Breach probability:
  P(breach) = count(output_t violates constraint) / N
```

Supported distributions:
- `fixed`: constant value
- `normal`: μ=value, σ=std (clipped at min/max if specified)
- `uniform`: U(min, max)
- `triangular`: Triang(min, mode, max)
- `lognormal`: parameterised from (value, std)

Maximum trials: 100,000. Reproducible via seed.

### C. Scenario Comparison

Evaluate the model at discrete scenario points (baseline, optimistic, pessimistic, or custom).
Auto-generated scenarios apply a multiplicative factor to all variables:
- Optimistic: 0.85× (15% better)
- Pessimistic: 1.20× (20% worse)

---

## Uncertainty Labelling

- **High confidence**: derived from model equations
- **Medium confidence**: estimated based on engineering judgement or historical patterns
- **Low confidence**: modelled with wide uncertainty bounds
- All assumptions are surfaced in the report

---

## Reproducibility

Every simulation run stores:
- `seed` (integer)
- `algorithm_version` (string, currently "1.0.0")
- `parameters` (full JSON)
- `created_at` timestamp

Given the same seed, domain, variables, and algorithm version, results are bit-for-bit identical.
