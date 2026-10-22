import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import VariableEditor from '../components/VariableEditor';
import AssumptionsPanel from '../components/AssumptionsPanel';
import SimulationResults from '../components/SimulationResults';

const DEMO_INPUT = "What if monthly cloud costs rise by 20%, user traffic doubles, and we need to maintain 99.9% availability?";

const METHOD_DESCRIPTIONS = {
  sensitivity: 'One-at-a-time sensitivity analysis — shows which variables have the biggest impact.',
  monte_carlo: 'Monte Carlo simulation — models uncertainty with probability distributions.',
  scenario_comparison: 'Compare baseline, optimistic, and pessimistic outcomes side-by-side.',
};

export default function Workspace() {
  const [rawInput, setRawInput] = useState('');
  const [seed, setSeed] = useState(42);
  const [phase, setPhase] = useState('input'); // input | variables | results
  const [interpreting, setInterpreting] = useState(false);
  const [running, setRunning] = useState(false);
  const [interpreted, setInterpreted] = useState(null);
  const [results, setResults] = useState(null);
  const [method, setMethod] = useState('scenario_comparison');
  const [nTrials, setNTrials] = useState(10000);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  async function handleInterpret() {
    if (!rawInput.trim()) { setError('Please enter a scenario.'); return; }
    setError('');
    setInterpreting(true);
    try {
      const result = await api.interpretScenario(rawInput, seed);
      setInterpreted(result);
      // Auto-choose method based on stochastic variables
      const stochasticCount = Object.values(result.variables || {}).filter(
        v => v?.dist && v.dist !== 'fixed'
      ).length;
      if (stochasticCount >= 2) setMethod('monte_carlo');
      else if (Object.keys(result.variables || {}).length >= 3) setMethod('sensitivity');
      else setMethod('scenario_comparison');
      setPhase('variables');
    } catch (e) {
      setError(e.message);
    } finally {
      setInterpreting(false);
    }
  }

  async function handleRun() {
    setError('');
    setRunning(true);
    try {
      const params = method === 'monte_carlo' ? { n_trials: nTrials } : {};
      const result = await api.quickRun(rawInput, seed);
      // Use the full workflow result
      setResults(result);
      setPhase('results');
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  async function handleRunWithVars() {
    // Run simulation with possibly-edited variables
    setError('');
    setRunning(true);
    try {
      const params = method === 'monte_carlo' ? { n_trials: nTrials } : {};
      // Build a full workflow result using interpreted vars
      const fullResult = {
        ...interpreted,
        simulation_method: method,
        simulation_result: null,
      };
      // Directly call quick-run (re-uses the NL input for now)
      const result = await api.quickRun(rawInput, seed);
      setResults(result);
      setPhase('results');
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  function handleVariableChange(varName, field, value) {
    setInterpreted(prev => ({
      ...prev,
      variables: {
        ...prev.variables,
        [varName]: { ...prev.variables[varName], [field]: parseFloat(value) || value },
      }
    }));
  }

  return (
    <div className="animate-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Scenario Workspace</h1>
          <p className="page-subtitle">Describe a hypothetical situation → get a simulation-based decision report</p>
        </div>
        <div className="flex gap-8">
          {phase !== 'input' && (
            <button className="btn btn-secondary btn-sm" onClick={() => { setPhase('input'); setInterpreted(null); setResults(null); }}>
              ↩ Reset
            </button>
          )}
        </div>
      </div>

      {/* Tab progress */}
      <div className="tab-bar mb-16">
        {['input', 'variables', 'results'].map((p, i) => (
          <button
            key={p}
            id={`workspace-tab-${p}`}
            className={`tab-btn ${phase === p ? 'active' : ''}`}
            onClick={() => { if (i === 0 || (i === 1 && interpreted) || (i === 2 && results)) setPhase(p); }}
            disabled={(i === 1 && !interpreted) || (i === 2 && !results)}
          >
            {i + 1}. {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
      </div>

      {error && <div className="alert alert-danger mb-16">⚠ {error}</div>}

      {/* Phase 1: Input */}
      {phase === 'input' && (
        <div className="workspace-layout">
          <div>
            <div className="card" style={{ marginBottom: 16 }}>
              <h3 style={{ marginBottom: 12 }}>Scenario Description</h3>
              <textarea
                id="scenario-nl-input"
                className="nl-input-area"
                placeholder="Describe your scenario in plain English…"
                value={rawInput}
                onChange={e => setRawInput(e.target.value)}
                rows={5}
              />
              <div className="flex justify-between items-center mt-16">
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setRawInput(DEMO_INPUT)}
                >
                  Load demo scenario
                </button>
                <div className="flex gap-8 items-center">
                  <label className="form-label" style={{ margin: 0 }}>Seed:</label>
                  <input
                    id="seed-input"
                    className="form-input"
                    style={{ width: 80 }}
                    type="number"
                    value={seed}
                    onChange={e => setSeed(Number(e.target.value))}
                  />
                  <button
                    id="interpret-btn"
                    className="btn btn-primary"
                    onClick={handleInterpret}
                    disabled={interpreting}
                  >
                    {interpreting ? '⏳ Interpreting…' : '🔍 Interpret'}
                  </button>
                </div>
              </div>
            </div>

            <div className="alert alert-info">
              The AI agent will extract variables from your scenario, identify assumptions,
              choose a simulation method, and run the analysis. All calculations use
              documented equations — no fabricated numbers.
            </div>
          </div>

          <div className="card">
            <h4 style={{ marginBottom: 16 }}>Example Scenarios</h4>
            {[
              "What if monthly cloud costs rise by 20%, user traffic doubles, and we need to maintain 99.9% availability?",
              "Our monthly spend is $15,000. Traffic will triple. We need 99.99% uptime.",
              "Cloud costs drop by 15% after renegotiation. Traffic grows 50%.",
            ].map((ex, i) => (
              <button
                key={i}
                className="btn btn-secondary w-full mb-8"
                style={{ textAlign: 'left', fontSize: '0.8rem', padding: '10px 12px' }}
                onClick={() => setRawInput(ex)}
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Phase 2: Variables */}
      {phase === 'variables' && interpreted && (
        <div className="workspace-layout">
          <div>
            <div className="card mb-16">
              <div className="flex justify-between items-center mb-16">
                <h3>Extracted Variables</h3>
                <span className="badge badge-info">{Object.keys(interpreted.variables || {}).length} variables</span>
              </div>
              <VariableEditor
                variables={interpreted.variables}
                onChange={handleVariableChange}
              />
            </div>

            <div className="card">
              <h3 style={{ marginBottom: 12 }}>Simulation Method</h3>
              {Object.entries(METHOD_DESCRIPTIONS).map(([m, desc]) => (
                <label
                  key={m}
                  className="card-elevated mb-8"
                  style={{ display: 'flex', gap: 12, alignItems: 'flex-start', cursor: 'pointer', border: method === m ? '1px solid var(--accent)' : undefined }}
                >
                  <input
                    type="radio"
                    name="method"
                    value={m}
                    checked={method === m}
                    onChange={() => setMethod(m)}
                    style={{ marginTop: 3 }}
                  />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 2 }}>{m.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}</div>
                    <div className="text-sm text-muted">{desc}</div>
                  </div>
                </label>
              ))}
              {method === 'monte_carlo' && (
                <div className="form-group mt-16">
                  <label className="form-label">Trials (max 100,000)</label>
                  <input
                    id="n-trials-input"
                    className="form-input"
                    type="number"
                    min={100}
                    max={100000}
                    value={nTrials}
                    onChange={e => setNTrials(Math.min(100000, parseInt(e.target.value) || 10000))}
                  />
                </div>
              )}
              <button
                id="run-simulation-btn"
                className="btn btn-primary w-full mt-16"
                onClick={handleRunWithVars}
                disabled={running}
              >
                {running ? '⚙️ Running simulation…' : '▶ Run Simulation'}
              </button>
            </div>
          </div>

          <div>
            <AssumptionsPanel assumptions={interpreted.assumptions} />
            {interpreted.clarification_questions?.length > 0 && (
              <div className="card mt-16">
                <h3 style={{ marginBottom: 12 }}>Clarification Needed</h3>
                {interpreted.clarification_questions.map((q, i) => (
                  <div key={i} className="assumption-item">❓ {q}</div>
                ))}
              </div>
            )}
            {interpreted.errors?.length > 0 && (
              <div className="card mt-16">
                <h3 style={{ marginBottom: 12 }}>Validation Issues</h3>
                {interpreted.errors.map((e, i) => (
                  <div key={i} className="alert alert-warning mb-8">⚠ {e}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Phase 3: Results */}
      {phase === 'results' && results && (
        <SimulationResults results={results} seed={seed} />
      )}
    </div>
  );
}
