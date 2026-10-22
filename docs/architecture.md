# WhatIf AI — Architecture Overview

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Browser (React)                                                       │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │Dashboard │ │ Workspace  │ │ Variables│ │ Charts   │ │Reports  │ │
│  └──────────┘ └────────────┘ └──────────┘ └──────────┘ └─────────┘ │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ REST / JSON
┌───────────────────────────────▼──────────────────────────────────────┐
│  Django REST Framework (Python)                                        │
│  ┌───────────┐ ┌──────────────┐ ┌─────────────────────────────────┐  │
│  │ Auth &    │ │  REST API    │ │  Multi-Agent Workflow           │  │
│  │ Token     │ │  ViewSets    │ │  (agents/workflow.py)           │  │
│  └───────────┘ └──────┬───────┘ └─────────────┬───────────────────┘  │
│                        │                        │                      │
│              ┌─────────▼─────────┐   ┌──────────▼────────────────┐   │
│              │   Django Models   │   │   Simulation Engine        │   │
│              │   (SQLite / PG)   │   │   (simulation/engine.py)   │   │
│              └───────────────────┘   └───────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                                        │
                              ┌─────────▼──────────┐
                              │  Ollama (optional)  │
                              │  Local LLM server   │
                              └────────────────────┘
```

## Components

### Frontend (React)
- **React Router** for client-side routing
- **Chart.js** for all simulation visualisations
- No Tailwind / Bootstrap — plain CSS with CSS variables
- API client in `frontend/src/api/client.js`

### Backend (Django REST Framework)
- Token-based authentication
- `api/` app with models, serialisers, views, URLs
- Rate throttling on all endpoints

### Simulation Engine (`backend/simulation/engine.py`)
- **No dynamic code execution** — all maths is fixed Python
- Three simulation modes: sensitivity, Monte Carlo, scenario comparison
- Reproducible via `numpy.random.default_rng(seed)`
- Fully documented equations in `docs/simulation_methodology.md`

### Multi-Agent Workflow (`backend/agents/workflow.py`)
Implemented as a deterministic state machine (LangGraph-style):

```
raw_input
    │
    ▼
scenario_interpreter   → extract NL → structured variables (LLM or heuristic)
    │
    ▼
assumption_validator   → check ranges, units, contradictions
    │
    ▼
simulation_planner     → choose method (sensitivity / MC / comparison)
    │
    ▼
simulation_executor    → call simulation/engine.py (no dynamic code)
    │
    ▼
risk_analyst           → evaluate outcomes vs constraints
    │
    ▼
decision_explainer     → generate explanation (LLM or template)
    │
    ▼
report_generator       → assemble final report JSON
```

Each node has a 30-second wall-clock limit and hard-stops after 5 errors.

### Database
- SQLite for development (zero configuration)
- PostgreSQL for production (via `DATABASE_URL` env var)
- Models: Project, ScenarioSpec, SimulationConfig, SimulationRun, RunMetric, SimulationResult, GeneratedReport

### LLM Integration
- Ollama HTTP API at `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- Configurable model via `OLLAMA_MODEL` (default: `qwen2.5:7b`)
- Fully graceful fallback when Ollama is unavailable
- LLM used ONLY for NL→variable extraction and explanation text
- All numerical computations use deterministic Python — LLM output is never executed

## Security Properties
- Input validation on all endpoints (DRF serialisers + model validators)
- Simulation bounds: max 100,000 Monte Carlo trials, 60s execution limit
- No model-generated code execution
- Token authentication required for write operations
- Secrets stored in `.env` (never committed)
- CORS configured via `CORS_ALLOWED_ORIGINS`
