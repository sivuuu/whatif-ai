# WhatIf AI — Enterprise Decision Intelligence Simulator

[![CI](https://github.com/whatif-ai/whatif-simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/whatif-ai/whatif-simulator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://python.org)
[![React: 18](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev)

> **WhatIf AI** is an open-source enterprise scenario-planning and decision-intelligence platform. It translates natural-language "what-if" operational scenarios into structured parametric models, executes deterministic and stochastic simulations (Sensitivity Analysis, Monte Carlo, Multi-Scenario Comparison), and generates transparent, traceable decision reports with explicit confidence scores and assumptions.

---

## 🌟 Key Features

- **Natural Language to Parametric Models**: Converts free-form operational questions into structured variables, probability distributions, and constraints using LangGraph and local LLMs (Ollama / Qwen) with robust heuristic fallbacks.
- **Traceable Assumptions & Confidence Scoring**: Every extracted variable is accompanied by an audit trail of assumptions, confidence levels (`high`, `medium`, `low`), and rationale.
- **Quantitative Simulation Engine**:
  - **Deterministic Sensitivity Analysis**: One-at-a-time (OAT) parameter variation measuring marginal cost and elasticity.
  - **Monte Carlo Simulation**: Stochastic sampling across normal, lognormal, uniform, and triangular distributions with reproducible seeds (`seed=42`).
  - **Multi-Scenario Comparison**: Direct side-by-side comparison of baseline, optimistic, and pessimistic projections.
- **Reproducibility Guarantee**: Every run produces an identical output given the same input parameters and random seed. Full execution provenance is stored with algorithm version, timestamp, and seed.
- **Enterprise Web Interface**: Responsive dark-mode UI with Chart.js visualizations, scenario workspace, live variable tuning, assumption review, and run history audit.
- **RESTful API**: Comprehensive Django REST Framework endpoints for CI/CD integration, headless simulations, and report exports.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Web UI (React 18)                         │
│   Dashboard  │  Workspace  │  Visualizations  │  Run History    │
└───────────────────────────────┬─────────────────────────────────┘
                                │ JSON / REST
┌───────────────────────────────▼─────────────────────────────────┐
│              Django REST Framework Backend                      │
│   /api/scenarios/  │  /api/runs/launch/  │  /api/stats/         │
└───────┬─────────────────────────────────────────────────┬───────┘
        │                                                 │
┌───────▼──────────────────────┐         ┌────────────────▼───────┐
│     LangGraph Orchestrator    │         │  Quantitative Engine   │
│  - Heuristic & LLM Extractor │         │  - Sensitivity (OAT)   │
│  - Validation & Assumptions  │         │  - Monte Carlo         │
│  - Decision Recommendation   │         │  - Scenario Comparison │
└───────────────┬──────────────┘         └────────────────┬───────┘
                │                                         │
        ┌───────▼───────┐                         ┌───────▼───────┐
        │  Ollama /     │                         │ NumPy, pandas │
        │  Local LLMs   │                         │ & SciPy       │
        └───────────────┘                         └───────────────┘
```

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

1. **Clone repository**:
   ```bash
   git clone https://github.com/whatif-ai/whatif-simulator.git
   cd whatif-simulator
   ```

2. **Start services**:
   ```bash
   docker-compose up --build
   ```

3. **Open application**:
   - Web UI: [http://localhost:3000](http://localhost:3000)
   - API Backend: [http://localhost:8000/api/](http://localhost:8000/api/)
   - Default Demo Credentials: `demo` / `whatif2024`

---

### Option 2: Local Development Setup

#### 1. Backend Setup (Python 3.11+)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt

# Run migrations and seed sample data
python manage.py migrate
python manage.py seed_data

# Start backend server
python manage.py runserver 8000
```

#### 2. Frontend Setup (Node.js 18+)

```bash
cd frontend
npm install
npm start
```

Visit [http://localhost:3000](http://localhost:3000) to access the interactive workspace.

---

## 📊 Simulation Methodology

For complete mathematical definitions, refer to [docs/simulation_methodology.md](docs/simulation_methodology.md).

### Cloud Infrastructure Model
- **Base Cost**: $C_0$
- **Traffic Multiplier**: $T$
- **Total Projected Cost**:
  $$\text{Cost} = C_0 \times (1 + \Delta_{\text{cost}}) \times (1 + 0.6 \times (T - 1)) + \text{StorageCost} + \text{EgressCost}$$
- **SLA Penalty**:
  $$\text{Cost}_{\text{final}} = \text{Cost} \times (1 + \text{PenaltyMultiplier})$$

### Supported Probability Distributions
- `fixed`: Constant value ($X = \mu$)
- `normal`: Gaussian distribution $\mathcal{N}(\mu, \sigma)$
- `lognormal`: Right-skewed distribution $\text{LogNormal}(\mu, \sigma)$
- `uniform`: Continuous bounded interval $\mathcal{U}(a, b)$
- `triangular`: Three-point estimation $\text{Triangular}(a, c, b)$

---

## 🧪 Testing and Verification

WhatIf AI includes an extensive automated test suite covering deterministic model mathematics, stochastic convergence, agent orchestration, and API endpoints.

```bash
# Run the complete test suite
source venv/bin/activate
DJANGO_SETTINGS_MODULE=whatif.settings pytest tests/ -v
```

Output:
```
=================== 67 passed, 2 skipped in 0.67s ===================
```

### Benchmark Evaluation Suite
The test suite validates 20 evaluation scenarios (`E01` through `E20`) covering:
- Baseline scale-ups
- Traffic shocks & viral spikes
- Multi-cloud migrations
- Cost reductions & optimizations
- SLA degradations & edge cases

---

## 📚 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/stats/` | System-wide statistics for scenarios and runs |
| `POST` | `/api/quick-run/` | Single-step scenario interpretation and simulation |
| `POST` | `/api/scenarios/interpret/` | Extract parametric variables and assumptions from text |
| `GET` | `/api/scenarios/` | List all saved scenarios |
| `POST` | `/api/runs/launch/` | Launch an asynchronous or synchronous simulation run |
| `GET` | `/api/runs/{id}/` | Retrieve run results, metadata, and execution time |
| `GET` | `/api/runs/{id}/compare/?other={other_id}` | Compare two simulation runs side-by-side |
| `POST` | `/api/runs/{id}/export_report/` | Export decision intelligence report (JSON format) |

---

## 📁 Repository Structure

```
.
├── Dockerfile.backend          # Backend container specification
├── Dockerfile.frontend         # Frontend multi-stage container
├── docker-compose.yml          # Production multi-service orchestration
├── docs/                       # Architectural and methodology documentation
│   ├── architecture.md
│   └── simulation_methodology.md
├── sample_scenarios/           # Sample JSON scenarios for evaluation
├── backend/
│   ├── agents/                 # LangGraph workflow & LLM / heuristic extractors
│   ├── api/                    # Django models, serializers, views, seed command
│   ├── evaluation/             # 20 evaluation benchmark scenarios
│   ├── simulation/             # Quantitative engines (Sensitivity, Monte Carlo)
│   └── whatif/                 # Django project settings and root URLs
├── frontend/
│   ├── public/                 # HTML shell and public assets
│   └── src/
│       ├── api/                # REST client library
│       ├── components/         # SimulationResults, VariableEditor, AssumptionsPanel
│       ├── context/            # AuthContext
│       └── pages/              # Dashboard, Workspace, History, Login
└── tests/                      # Pytest test suite (67 unit & integration tests)
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
