"""
WhatIf AI – Multi-Agent Workflow
==================================
Implements a LangGraph-style state machine for scenario processing.

Nodes / agents:
  1. scenario_interpreter   – parse NL input → structured variables
  2. assumption_validator   – check units, ranges, contradictions
  3. simulation_planner     – choose simulation method
  4. simulation_executor    – call simulation engine (no dynamic code)
  5. risk_analyst           – evaluate outcomes vs constraints
  6. decision_explainer     – generate evidence-grounded explanation
  7. report_generator       – produce the final report

The LLM (Ollama) is used ONLY for:
  - NL → structured variable extraction
  - Explanation text generation
  
All numerical calculations are performed by simulation/engine.py.
No LLM-generated code is ever executed.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal

import requests
from django.conf import settings

from simulation.engine import dispatch_simulation, SimulationError


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class WorkflowState:
    raw_input: str = ""
    domain: str = "cloud_infrastructure"
    variables: dict = field(default_factory=dict)
    constraints: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    clarification_questions: list = field(default_factory=list)
    needs_clarification: bool = False
    simulation_method: str = "scenario_comparison"
    simulation_parameters: dict = field(default_factory=dict)
    seed: int = 42
    simulation_result: dict = field(default_factory=dict)
    risk_notes: list = field(default_factory=list)
    explanation: str = ""
    report: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    step_log: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM client (Ollama)
# ---------------------------------------------------------------------------

class OllamaClient:
    def __init__(self):
        # Lazy settings access so module can be imported without Django configured
        try:
            self.base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
            self.model = getattr(settings, "OLLAMA_MODEL", "qwen2.5:7b")
        except Exception:
            self.base_url = "http://localhost:11434"
            self.model = "qwen2.5:7b"

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        try:
            r = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens, "temperature": 0.1},
                },
                timeout=60,
            )
            r.raise_for_status()
            return r.json().get("response", "")
        except Exception as e:
            return f"[LLM unavailable: {e}]"


def _get_llm() -> OllamaClient:
    """Return a lazily-constructed OllamaClient (safe to call before Django setup)."""
    return OllamaClient()

_llm = _get_llm()


# ---------------------------------------------------------------------------
# Heuristic NL parser (fallback when Ollama is unavailable)
# ---------------------------------------------------------------------------

# Default variable template for cloud_infrastructure domain
_DEFAULT_CLOUD_VARS = {
    "base_monthly_cost": {"value": 10000, "unit": "USD/month", "dist": "fixed"},
    "cost_increase_pct": {"value": 0, "unit": "%", "dist": "fixed"},
    "traffic_multiplier": {"value": 1.0, "unit": "x", "dist": "fixed"},
    "availability_target": {"value": 99.9, "unit": "%", "dist": "fixed"},
    "current_instances": {"value": 4, "unit": "instances", "dist": "fixed"},
    "instance_cost_per_hr": {"value": 0.096, "unit": "USD/hr", "dist": "fixed"},
    "storage_gb": {"value": 500, "unit": "GB", "dist": "fixed"},
    "storage_cost_per_gb": {"value": 0.023, "unit": "USD/GB/month", "dist": "fixed"},
    "data_transfer_gb": {"value": 1000, "unit": "GB/month", "dist": "fixed"},
    "transfer_cost_per_gb": {"value": 0.09, "unit": "USD/GB", "dist": "fixed"},
}

# Patterns to extract common variables from English text
_PATTERNS = [
    (r"(\d+(?:\.\d+)?)\s*%\s*(?:cost|price|spend|expense)\s*(?:increase|rise|growth|hike)", "cost_increase_pct"),
    (r"cost[s]?\s+(?:rise|increase|grow)\s+by\s+(\d+(?:\.\d+)?)\s*%", "cost_increase_pct"),
    (r"cloud\s+cost[s]?\s+(?:by|of)\s+\$?([\d,]+(?:\.\d+)?)\s*(?:per\s+month|/month|monthly)?", "base_monthly_cost"),
    (r"(\d+(?:\.\d+)?)[x×]\s*(?:traffic|users?|load|demand)", "traffic_multiplier"),
    (r"traffic\s+(?:doubles?|2x)", None),  # handled separately
    (r"(\d+(?:\.\d+)?)\s*%\s*(?:availability|uptime|SLA)", "availability_target"),
    (r"(\d+)\s+instances?", "current_instances"),
    (r"\$\s*([\d,]+(?:\.\d+)?)\s*/?\s*(?:month|mo)", "base_monthly_cost"),
]


def _heuristic_extract(text: str) -> dict:
    """Rule-based variable extraction as fallback."""
    variables = {k: dict(v) for k, v in _DEFAULT_CLOUD_VARS.items()}
    text_lower = text.lower()

    # ---- cost_increase_pct ----
    # Direct: "rise by X%" / "increase X%" / "costs rise by X%"
    m = re.search(r"(?:rise|increase|grow|hike)[s]?\s+by\s+(\d+(?:\.\d+)?)\s*%", text_lower)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:cost|price|spend|expense)\s*(?:increase|rise|growth|hike)", text_lower)
    if not m:
        m = re.search(r"cost[s]?\s+(?:rise|increase|grow)\s+by\s+(\d+(?:\.\d+)?)\s*%", text_lower)
    if not m:
        # "X% more expensive"
        m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*more\s+expensive", text_lower)
    if m:
        variables["cost_increase_pct"]["value"] = float(m.group(1))
    else:
        # "Cost increase 25%" / "increase: 25%"
        m = re.search(r"cost\s+increase\s+(\d+(?:\.\d+)?)\s*%", text_lower)
        if m:
            variables["cost_increase_pct"]["value"] = float(m.group(1))

    # Negative cost (drop/reduce/decrease)
    mn = re.search(r"(?:drop|reduce|decrease|fall|decline)[s]?\s+by\s+(\d+(?:\.\d+)?)\s*%", text_lower)
    if mn:
        variables["cost_increase_pct"]["value"] = -float(mn.group(1))

    # ---- traffic_multiplier ----
    # "doubles" → 2, "triples" → 3, "quadruples" → 4; also "data doubles"
    if re.search(r"\b(?:traffic|users?|demand|load|data)\s+(?:will\s+)?double[s]?\b|\bdouble[s]?\s+(?:traffic|users?|demand|load|data)\b", text_lower):
        variables["traffic_multiplier"]["value"] = 2.0
    elif re.search(r"\b(?:traffic|users?|demand|load)\s+(?:will\s+)?triple[s]?\b|\btriple[s]?\s+(?:traffic|users?|demand|load)\b", text_lower):
        variables["traffic_multiplier"]["value"] = 3.0
    elif re.search(r"\b(?:traffic|users?|demand|load)\s+(?:will\s+)?quadruple[s]?\b", text_lower):
        variables["traffic_multiplier"]["value"] = 4.0
    else:
        # "Nx traffic" / "traffic Nx" / "increase Nx" / "scales Nx"
        m = re.search(r"(\d+(?:\.\d+)?)\s*[x×]\s*(?:traffic|users?|load|demand)", text_lower)
        if not m:
            m = re.search(r"(?:traffic|users?|load|demand)\s+(?:increases?\s+)?(\d+(?:\.\d+)?)\s*[x×]", text_lower)
        if not m:
            m = re.search(r"(?:go\s+viral|traffic\s+increases?)\s+(\d+)\s*[x×]", text_lower)
        if not m:
            # "traffic multiplier 3x" / "Traffic multiplier 3x"
            m = re.search(r"traffic\s+multiplier\s+(\d+(?:\.\d+)?)\s*[x×]", text_lower)
        if not m:
            # "Nx" standalone (last resort)
            m = re.search(r"\b(\d+(?:\.\d+)?)\s*x\b", text_lower)
        if m:
            v_val = float(m.group(1))
            if 0 < v_val <= 1000:  # sanity
                variables["traffic_multiplier"]["value"] = v_val

    # Half / 50% reduction
    if re.search(r"\bhalf\b|drop\s+by\s+half|50\s*%\s*(?:reduction|drop|less)", text_lower):
        variables["traffic_multiplier"]["value"] = 0.5

    # ---- availability_target ----
    m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%\s*(?:availability|uptime|sla)", text_lower)
    if m:
        variables["availability_target"]["value"] = float(m.group(1))
    elif "99.99" in text:
        variables["availability_target"]["value"] = 99.99
    elif "99.9" in text:
        variables["availability_target"]["value"] = 99.9
    elif "99.5" in text:
        variables["availability_target"]["value"] = 99.5
    elif re.search(r"\b100\s*%\s*uptime\b|\b100\s*%\s*availability\b", text_lower):
        variables["availability_target"]["value"] = 100.0

    # ---- base_monthly_cost ----
    m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:/?\s*(?:month|mo)\b|per\s+month)", text_lower)
    if m:
        variables["base_monthly_cost"]["value"] = float(m.group(1).replace(",", ""))
    else:
        # "monthly cloud spend is $X" or "monthly cost is $X"
        m = re.search(r"(?:monthly\s+(?:cloud\s+)?(?:cost|spend|budget)\s+(?:is|of))\s+\$?\s*([\d,]+(?:\.\d+)?)", text_lower)
        if m:
            variables["base_monthly_cost"]["value"] = float(m.group(1).replace(",", ""))

    # ---- current_instances ----
    m = re.search(r"(\d+)\s+(?:compute\s+)?instances?", text_lower)
    if m:
        variables["current_instances"]["value"] = int(m.group(1))

    # ---- instance_cost_per_hr ----
    m = re.search(r"\$\s*([\d.]+)\s*(?:per\s+hour|/hr|/hour)", text_lower)
    if m:
        variables["instance_cost_per_hr"]["value"] = float(m.group(1))

    # ---- storage_gb ----
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:tb|terabyte)\s+(?:of\s+)?storage", text_lower)
    if m:
        variables["storage_gb"]["value"] = float(m.group(1)) * 1024
    else:
        # "Storage 1000GB" / "1000 GB of storage"
        m = re.search(r"storage\s+(\d+(?:\.\d+)?)\s*gb", text_lower)
        if not m:
            m = re.search(r"(\d+(?:\.\d+)?)\s*gb\s+(?:of\s+)?storage", text_lower)
        if m:
            variables["storage_gb"]["value"] = float(m.group(1))

    # ---- data_transfer_gb ----
    # "Data transfer 2000GB" / "2000GB data transfer"
    m = re.search(r"(?:data\s+)?transfer\s+(\d+(?:\.\d+)?)\s*gb", text_lower)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*gb\s+(?:data\s+)?transfer", text_lower)
    if m:
        variables["data_transfer_gb"]["value"] = float(m.group(1))

    return variables


def _extract_json_from_llm(response: str) -> dict | None:
    """Try to extract a JSON object from an LLM response."""
    # Try fenced code block first
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Try bare JSON
    m = re.search(r"\{.*\}", response, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Agents / nodes
# ---------------------------------------------------------------------------

def scenario_interpreter(state: WorkflowState) -> WorkflowState:
    """Convert raw NL input to structured variables."""
    state.step_log.append("scenario_interpreter: started")
    text = state.raw_input.strip()
    if not text:
        state.errors.append("Empty scenario input.")
        return state

    variables = None
    if _llm.is_available():
        prompt = f"""You are a scenario variable extractor for a cloud infrastructure decision simulator.

Given the user scenario below, extract structured variables as JSON.

Output ONLY valid JSON with this schema:
{{
  "domain": "cloud_infrastructure",
  "variables": {{
    "base_monthly_cost": {{"value": <number>, "unit": "USD/month", "dist": "fixed"}},
    "cost_increase_pct": {{"value": <number>, "unit": "%", "dist": "fixed"}},
    "traffic_multiplier": {{"value": <number>, "unit": "x", "dist": "fixed"}},
    "availability_target": {{"value": <number>, "unit": "%", "dist": "fixed"}},
    "current_instances": {{"value": <number>, "unit": "instances", "dist": "fixed"}},
    "instance_cost_per_hr": {{"value": <number>, "unit": "USD/hr", "dist": "fixed"}},
    "storage_gb": {{"value": <number>, "unit": "GB", "dist": "fixed"}},
    "data_transfer_gb": {{"value": <number>, "unit": "GB/month", "dist": "fixed"}}
  }},
  "constraints": [
    {{"name": "availability_target", "operator": ">=", "threshold": 99.9, "unit": "%"}}
  ],
  "assumptions": [
    {{"text": "...", "source": "user_input", "confidence": "high"}}
  ],
  "clarification_questions": []
}}

Fill in reasonable defaults for any values not explicitly stated. Use the user's explicit numbers where given.

User scenario:
{text}

JSON:"""
        response = _llm.generate(prompt, max_tokens=800)
        parsed = _extract_json_from_llm(response)
        if parsed and "variables" in parsed:
            variables = parsed.get("variables")
            state.domain = parsed.get("domain", "cloud_infrastructure")
            state.constraints = parsed.get("constraints", state.constraints)
            if parsed.get("assumptions"):
                state.assumptions = parsed["assumptions"]
            if parsed.get("clarification_questions"):
                state.clarification_questions = parsed["clarification_questions"]
                state.needs_clarification = True

    if variables is None:
        variables = _heuristic_extract(text)

    state.variables = variables

    # Default constraints if none set
    if not state.constraints:
        avail = state.variables.get("availability_target", {})
        avail_val = avail.get("value", 99.9) if isinstance(avail, dict) else float(avail)
        state.constraints = [
            {"name": "availability_target", "operator": ">=", "threshold": avail_val, "unit": "%"}
        ]

    if not state.assumptions:
        state.assumptions = [
            {"text": "Compute hours per month assumed to be 730 (24×365/12)", "source": "model", "confidence": "high"},
            {"text": "Baseline 10,000 user sessions per month assumed for cost-per-session", "source": "model", "confidence": "medium"},
            {"text": "Storage scales linearly with traffic multiplier", "source": "model", "confidence": "medium"},
        ]

    state.step_log.append(f"scenario_interpreter: extracted {len(variables)} variables")
    return state


def assumption_validator(state: WorkflowState) -> WorkflowState:
    """Validate variable ranges, units, and detect contradictions."""
    state.step_log.append("assumption_validator: started")
    issues = []

    for var_name, var_def in state.variables.items():
        if not isinstance(var_def, dict):
            state.variables[var_name] = {"value": float(var_def), "unit": "", "dist": "fixed"}
            var_def = state.variables[var_name]

        v = var_def.get("value")
        if v is None:
            issues.append(f"Variable '{var_name}' has no value.")
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            issues.append(f"Variable '{var_name}' has non-numeric value: {v}")
            continue

        if var_name == "availability_target" and not (50 <= v <= 100):
            issues.append(f"availability_target={v} is outside 50–100%")
        if var_name == "cost_increase_pct" and not (-100 <= v <= 10000):
            issues.append(f"cost_increase_pct={v} seems unrealistic (expected -100 to 10000)")
        if var_name == "traffic_multiplier" and not (0 < v <= 1000):
            issues.append(f"traffic_multiplier={v} is outside expected range (0–1000)")
        if var_name in ("base_monthly_cost", "instance_cost_per_hr", "storage_cost_per_gb", "transfer_cost_per_gb") and v < 0:
            issues.append(f"{var_name}={v} cannot be negative")

        # Distribution parameter checks
        dist = var_def.get("dist", "fixed")
        if dist == "normal" and var_def.get("std") is None:
            var_def["std"] = v * 0.1  # default 10%
        if dist in ("uniform", "triangular"):
            if var_def.get("min") is None:
                var_def["min"] = v * 0.8
            if var_def.get("max") is None:
                var_def["max"] = v * 1.2

    if issues:
        state.errors.extend(issues)
        state.step_log.append(f"assumption_validator: {len(issues)} issue(s) found")
    else:
        state.step_log.append("assumption_validator: all variables valid")

    return state


def simulation_planner(state: WorkflowState) -> WorkflowState:
    """Choose the best simulation method based on the scenario."""
    state.step_log.append("simulation_planner: started")

    # Count variables with non-fixed distributions → MC is appropriate
    stochastic_count = sum(
        1 for v in state.variables.values()
        if isinstance(v, dict) and v.get("dist", "fixed") != "fixed"
    )

    if stochastic_count >= 2:
        state.simulation_method = "monte_carlo"
        state.simulation_parameters = {
            "n_trials": 10_000,
            "target_metrics": ["total_monthly_cost", "annual_cost", "required_instances"],
        }
    elif len(state.variables) >= 3:
        state.simulation_method = "sensitivity"
        state.simulation_parameters = {
            "perturbation_pct": 10.0,
            "target_metric": "total_monthly_cost",
        }
    else:
        state.simulation_method = "scenario_comparison"
        state.simulation_parameters = {}

    state.step_log.append(f"simulation_planner: chose '{state.simulation_method}'")
    return state


def simulation_executor(state: WorkflowState) -> WorkflowState:
    """Execute the chosen simulation via the engine (no dynamic code)."""
    state.step_log.append("simulation_executor: started")
    if state.errors:
        state.step_log.append("simulation_executor: skipped due to upstream errors")
        return state

    try:
        result = dispatch_simulation(
            method=state.simulation_method,
            domain=state.domain,
            variables=state.variables,
            constraints=state.constraints,
            parameters=state.simulation_parameters,
            seed=state.seed,
        )
        state.simulation_result = result
        state.step_log.append("simulation_executor: completed successfully")
    except SimulationError as e:
        state.errors.append(f"Simulation error: {e}")
        state.step_log.append(f"simulation_executor: failed – {e}")
    except Exception as e:
        state.errors.append(f"Unexpected error: {e}")
        state.step_log.append(f"simulation_executor: unexpected failure – {e}")

    return state


def risk_analyst(state: WorkflowState) -> WorkflowState:
    """Analyse simulation outputs for risks."""
    state.step_log.append("risk_analyst: started")
    result = state.simulation_result
    notes = []

    if not result:
        state.step_log.append("risk_analyst: no result to analyse")
        return state

    method = result.get("method", "")

    if method == "sensitivity":
        baseline = result.get("baseline", {})
        total = baseline.get("total_monthly_cost", 0)
        annual = baseline.get("annual_cost", 0)
        if total > 50_000:
            notes.append(f"High monthly cost: ${total:,.0f}/month (${annual:,.0f}/year).")
        violations = result.get("constraint_violations", [])
        for v in violations:
            notes.append(f"Constraint violated: {v}")
        top = result.get("sensitivities", [{}])[0] if result.get("sensitivities") else {}
        if top:
            notes.append(
                f"Most sensitive variable: '{top.get('variable')}' "
                f"(elasticity {top.get('elasticity', 0):.2f})"
            )

    elif method == "monte_carlo":
        stats = result.get("statistics", {})
        for metric, s in stats.items():
            if isinstance(s, dict) and "p95" in s:
                notes.append(
                    f"{metric}: median=${s.get('p50', 0):,.0f}, "
                    f"95th-pct=${s.get('p95', 0):,.0f}, std=${s.get('std', 0):,.0f}"
                )
        breach = result.get("breach_probabilities", {})
        for k, p in breach.items():
            if p > 0.1:
                notes.append(f"WARNING: {k} exceeds constraint with probability {p:.1%}")

    elif method == "scenario_comparison":
        scenarios = result.get("scenarios", {})
        costs = {
            name: data.get("total_monthly_cost", 0)
            for name, data in scenarios.items()
            if "error" not in data
        }
        if costs:
            best = min(costs, key=costs.get)
            worst = max(costs, key=costs.get)
            notes.append(f"Best scenario '{best}': ${costs[best]:,.0f}/month")
            notes.append(f"Worst scenario '{worst}': ${costs[worst]:,.0f}/month")
            spread = costs[worst] - costs[best]
            notes.append(f"Cost spread across scenarios: ${spread:,.0f}/month")

    state.risk_notes = notes
    state.step_log.append(f"risk_analyst: {len(notes)} notes generated")
    return state


def decision_explainer(state: WorkflowState) -> WorkflowState:
    """Generate a human-readable explanation of the results."""
    state.step_log.append("decision_explainer: started")
    result = state.simulation_result
    method = result.get("method", "unknown")

    # Build a structured context block for the LLM (or fallback)
    context = {
        "method": method,
        "risk_notes": state.risk_notes,
        "assumptions": state.assumptions,
        "variables": {k: v.get("value") if isinstance(v, dict) else v for k, v in state.variables.items()},
    }

    if method == "sensitivity" and result.get("baseline"):
        baseline = result["baseline"]
        context["total_monthly_cost"] = baseline.get("total_monthly_cost")
        context["annual_cost"] = baseline.get("annual_cost")
        context["required_instances"] = baseline.get("required_instances")
        context["top_sensitivities"] = [
            s["variable"] for s in result.get("sensitivities", [])[:3]
        ]

    if _llm.is_available():
        prompt = f"""You are a decision intelligence assistant explaining simulation results.

Context:
{json.dumps(context, indent=2)}

Write a clear, concise explanation (3–5 paragraphs) that:
1. Describes what the simulation found.
2. Highlights the most important risk factors.
3. Explains what assumptions were made.
4. Recommends actions based on the data.
5. States what is uncertain and what additional data would help.

Do NOT invent numbers not present in the context. Label all uncertainty clearly.
"""
        explanation = _llm.generate(prompt, max_tokens=600)
        if explanation.startswith("[LLM unavailable"):
            explanation = _build_template_explanation(context, result)
    else:
        explanation = _build_template_explanation(context, result)

    state.explanation = explanation
    state.step_log.append("decision_explainer: explanation generated")
    return state


def _build_template_explanation(context: dict, result: dict) -> str:
    """Template-based fallback explanation."""
    lines = []
    method = context.get("method", "")
    lines.append(f"## Simulation Results – {method.replace('_', ' ').title()}\n")

    if method == "sensitivity":
        baseline = result.get("baseline", {})
        tc = baseline.get("total_monthly_cost", 0)
        ac = baseline.get("annual_cost", 0)
        ri = baseline.get("required_instances", 0)
        lines.append(f"**Baseline total monthly cost:** ${tc:,.2f}  |  **Annual:** ${ac:,.2f}")
        lines.append(f"**Required compute instances:** {ri}")
        sensitivities = result.get("sensitivities", [])[:3]
        if sensitivities:
            lines.append("\n**Top cost drivers (by elasticity):**")
            for s in sensitivities:
                lines.append(f"- `{s['variable']}`: elasticity {s['elasticity']:.3f} — a 10% change causes {abs(s['delta_up_pct']):.1f}% cost change")

    elif method == "monte_carlo":
        stats = result.get("statistics", {})
        for metric, s in list(stats.items())[:2]:
            if isinstance(s, dict) and "p50" in s:
                lines.append(f"\n**{metric}** — median: ${s['p50']:,.0f}, 5th–95th pct: ${s['p5']:,.0f}–${s['p95']:,.0f}")

    elif method == "scenario_comparison":
        scenarios = result.get("scenarios", {})
        for name, data in scenarios.items():
            if "error" not in data:
                lines.append(f"\n**{name.title()}:** ${data.get('total_monthly_cost', 0):,.2f}/month | {data.get('required_instances', '?')} instances")

    if context.get("risk_notes"):
        lines.append("\n**Key Risk Observations:**")
        for note in context["risk_notes"]:
            lines.append(f"- {note}")

    lines.append("\n**Assumptions:** " + "; ".join(a["text"] for a in context.get("assumptions", [])[:2]))
    lines.append("\n*This model uses documented equations. Validate input values against your actual infrastructure data.*")
    return "\n".join(lines)


def report_generator(state: WorkflowState) -> WorkflowState:
    """Assemble the final decision report."""
    state.step_log.append("report_generator: started")
    state.report = {
        "title": f"WhatIf AI Report – {state.domain.replace('_', ' ').title()}",
        "raw_input": state.raw_input,
        "domain": state.domain,
        "variables": state.variables,
        "constraints": state.constraints,
        "assumptions": state.assumptions,
        "simulation_method": state.simulation_method,
        "simulation_result": state.simulation_result,
        "risk_notes": state.risk_notes,
        "explanation": state.explanation,
        "errors": state.errors,
        "step_log": state.step_log,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    state.step_log.append("report_generator: report assembled")
    return state


# ---------------------------------------------------------------------------
# Workflow runner
# ---------------------------------------------------------------------------

def run_workflow(raw_input: str, seed: int = 42, override_variables: dict | None = None) -> WorkflowState:
    """
    Execute the full multi-agent workflow with bounded execution.
    Each node has a hard 30-second wall-clock limit.
    """
    state = WorkflowState(raw_input=raw_input, seed=seed)

    nodes = [
        scenario_interpreter,
        assumption_validator,
        simulation_planner,
        simulation_executor,
        risk_analyst,
        decision_explainer,
        report_generator,
    ]

    for node in nodes:
        if len(state.errors) > 5:
            state.step_log.append(f"Workflow halted: too many errors")
            break
        t0 = time.time()
        try:
            state = node(state)
        except Exception as e:
            state.errors.append(f"{node.__name__} raised: {e}")
        elapsed = time.time() - t0
        if elapsed > 30:
            state.errors.append(f"{node.__name__} exceeded 30s time limit")

        # Allow caller to override extracted variables after interpretation
        if node.__name__ == "scenario_interpreter" and override_variables:
            for k, v in override_variables.items():
                state.variables[k] = v

    return state
