import React, { useEffect, useRef, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Filler,
  Title, Tooltip, Legend,
} from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';
import AssumptionsPanel from './AssumptionsPanel';

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Filler,
  Title, Tooltip, Legend
);

const CHART_COLORS = {
  primary: '#6366f1',
  secondary: '#06b6d4',
  success: '#10b981',
  warn: '#f59e0b',
  danger: '#ef4444',
  muted: '#4a5568',
};

function fmt(val, unit = '') {
  if (typeof val !== 'number' || isNaN(val)) return '—';
  if (unit.toLowerCase().includes('usd') || unit === '$') return `$${val.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  return `${val.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`.trim();
}

// ─── Sensitivity Analysis View ───────────────────────────────────────────────
function SensitivityView({ result }) {
  const baseline = result.baseline || {};
  const sensitivities = result.sensitivities || [];
  const tornado = result.tornado || [];

  const chartData = {
    labels: sensitivities.slice(0, 8).map(s => s.variable),
    datasets: [
      {
        label: '+10% perturbation',
        data: sensitivities.slice(0, 8).map(s => s.delta_up_pct),
        backgroundColor: CHART_COLORS.primary + 'cc',
        borderRadius: 4,
      },
      {
        label: '-10% perturbation',
        data: sensitivities.slice(0, 8).map(s => s.delta_down_pct),
        backgroundColor: CHART_COLORS.secondary + 'cc',
        borderRadius: 4,
      },
    ],
  };

  const chartOpts = {
    responsive: true,
    indexAxis: 'y',
    plugins: {
      legend: { labels: { color: '#8b9fc9' } },
      tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.raw.toFixed(2)}%` } },
    },
    scales: {
      x: { ticks: { color: '#8b9fc9' }, grid: { color: 'rgba(99,130,201,0.1)' }, title: { display: true, text: '% Change in Total Monthly Cost', color: '#8b9fc9' } },
      y: { ticks: { color: '#8b9fc9' }, grid: { display: false } },
    },
  };

  return (
    <div className="animate-in">
      <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))' }}>
        {Object.entries(baseline).slice(0, 6).map(([k, v]) => (
          typeof v === 'number' && (
            <div key={k} className="stat-card">
              <div className="stat-value" style={{ fontSize: '1.3rem' }}>
                {k.includes('cost') || k.includes('annual') ? `$${Number(v).toLocaleString()}` :
                 k.includes('pct') ? `${v}%` : v.toLocaleString()}
              </div>
              <div className="stat-label">{k.replace(/_/g, ' ')}</div>
            </div>
          )
        ))}
      </div>

      <div className="card mt-24">
        <h3 style={{ marginBottom: 16 }}>Sensitivity Analysis — Tornado Chart</h3>
        <p style={{ marginBottom: 16, fontSize: '0.85rem' }}>% change in total monthly cost when each variable is perturbed by ±10%</p>
        <div className="chart-wrap" style={{ maxHeight: 400 }}>
          <Bar data={chartData} options={chartOpts} />
        </div>
      </div>

      <div className="card mt-24">
        <h3 style={{ marginBottom: 16 }}>Elasticity Rankings</h3>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Variable</th>
                <th>Elasticity</th>
                <th>+10% Impact</th>
                <th>-10% Impact</th>
              </tr>
            </thead>
            <tbody>
              {sensitivities.map((s, i) => (
                <tr key={s.variable}>
                  <td className="text-muted">#{i + 1}</td>
                  <td className="var-name">{s.variable}</td>
                  <td style={{ color: s.elasticity > 0 ? CHART_COLORS.danger : CHART_COLORS.success }}>
                    {s.elasticity.toFixed(3)}
                  </td>
                  <td className="text-sm" style={{ color: s.delta_up_pct > 0 ? CHART_COLORS.warn : CHART_COLORS.success }}>
                    {s.delta_up_pct > 0 ? '+' : ''}{s.delta_up_pct.toFixed(2)}%
                  </td>
                  <td className="text-sm" style={{ color: s.delta_down_pct < 0 ? CHART_COLORS.success : CHART_COLORS.warn }}>
                    {s.delta_down_pct > 0 ? '+' : ''}{s.delta_down_pct.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─── Monte Carlo View ────────────────────────────────────────────────────────
function MonteCarloView({ result }) {
  const stats = result.statistics || {};
  const histogram = result.histogram || {};
  const breachProbs = result.breach_probabilities || {};

  const histData = {
    labels: histogram.edges ? histogram.edges.slice(0, -1).map(e => `$${e.toLocaleString()}`) : [],
    datasets: [{
      label: 'Trial Count',
      data: histogram.counts || [],
      backgroundColor: CHART_COLORS.primary + 'aa',
      borderColor: CHART_COLORS.primary,
      borderWidth: 1,
    }],
  };

  const histOpts = {
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { title: ctx => `~$${histogram.edges?.[ctx[0].dataIndex]?.toLocaleString()}` } },
    },
    scales: {
      x: { ticks: { color: '#8b9fc9', maxTicksLimit: 10 }, grid: { color: 'rgba(99,130,201,0.1)' } },
      y: { ticks: { color: '#8b9fc9' }, grid: { color: 'rgba(99,130,201,0.1)' } },
    },
  };

  return (
    <div className="animate-in">
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-value" style={{ fontSize: '1.3rem', color: 'var(--accent-3)' }}>
            ${(stats.total_monthly_cost?.p50 ?? 0).toLocaleString()}
          </div>
          <div className="stat-label">Median Monthly Cost (p50)</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ fontSize: '1.3rem', color: 'var(--accent-warn)' }}>
            ${(stats.total_monthly_cost?.p95 ?? 0).toLocaleString()}
          </div>
          <div className="stat-label">95th Percentile Cost</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ fontSize: '1.3rem' }}>
            ${(stats.total_monthly_cost?.std ?? 0).toLocaleString()}
          </div>
          <div className="stat-label">Std Deviation</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ fontSize: '1.3rem' }}>{result.n_trials?.toLocaleString()}</div>
          <div className="stat-label">Trials (seed {result.seed})</div>
        </div>
      </div>

      <div className="card mt-24">
        <h3 style={{ marginBottom: 8 }}>Total Monthly Cost Distribution</h3>
        <p style={{ marginBottom: 16, fontSize: '0.85rem' }}>Histogram of {result.n_trials?.toLocaleString()} Monte Carlo trials</p>
        <div className="chart-wrap" style={{ maxHeight: 320 }}>
          <Bar data={histData} options={histOpts} />
        </div>
      </div>

      <div className="grid-2 mt-24">
        {Object.entries(stats).map(([metric, s]) => (
          typeof s === 'object' && s.p50 != null && (
            <div key={metric} className="card">
              <h4 style={{ marginBottom: 12 }}>{metric.replace(/_/g, ' ')}</h4>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                {['p5', 'p25', 'p50', 'p75', 'p95'].map(pct => (
                  <div key={pct} style={{ textAlign: 'center', flex: 1 }}>
                    <div style={{ fontSize: '0.9rem', fontWeight: 700, color: pct === 'p50' ? 'var(--accent)' : 'var(--text-primary)' }}>
                      {s[pct] > 100 ? `$${s[pct].toLocaleString()}` : s[pct].toLocaleString()}
                    </div>
                    <div className="text-xs text-muted">{pct.replace('p', '') + 'th'}</div>
                  </div>
                ))}
              </div>
            </div>
          )
        ))}
      </div>

      {Object.keys(breachProbs).length > 0 && (
        <div className="card mt-24">
          <h3 style={{ marginBottom: 12 }}>Constraint Breach Probabilities</h3>
          {Object.entries(breachProbs).map(([k, p]) => (
            <div key={k} style={{ marginBottom: 12 }}>
              <div className="flex justify-between mb-8">
                <span className="text-sm">{k}</span>
                <span className={`text-sm font-mono ${p > 0.5 ? 'text-danger' : p > 0.1 ? 'text-warn' : 'text-success'}`}>
                  {(p * 100).toFixed(1)}%
                </span>
              </div>
              <div className="progress-track">
                <div className="progress-fill" style={{
                  width: `${p * 100}%`,
                  background: p > 0.5 ? 'var(--accent-danger)' : p > 0.1 ? 'var(--accent-warn)' : 'var(--accent-3)',
                }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Scenario Comparison View ────────────────────────────────────────────────
function ScenarioComparisonView({ result }) {
  const scenarios = result.scenarios || {};
  const series = result.series || {};
  const scenarioNames = Object.keys(scenarios);

  const SCENARIO_COLORS = [CHART_COLORS.primary, CHART_COLORS.success, CHART_COLORS.danger, CHART_COLORS.warn];

  const costData = {
    labels: scenarioNames.map(n => n.charAt(0).toUpperCase() + n.slice(1)),
    datasets: [{
      label: 'Total Monthly Cost ($)',
      data: scenarioNames.map(n => scenarios[n]?.total_monthly_cost ?? 0),
      backgroundColor: scenarioNames.map((_, i) => SCENARIO_COLORS[i % SCENARIO_COLORS.length] + 'cc'),
      borderColor: scenarioNames.map((_, i) => SCENARIO_COLORS[i % SCENARIO_COLORS.length]),
      borderWidth: 2,
      borderRadius: 6,
    }],
  };

  const instanceData = {
    labels: scenarioNames.map(n => n.charAt(0).toUpperCase() + n.slice(1)),
    datasets: [{
      label: 'Required Instances',
      data: scenarioNames.map(n => scenarios[n]?.required_instances ?? 0),
      backgroundColor: scenarioNames.map((_, i) => SCENARIO_COLORS[i % SCENARIO_COLORS.length] + 'cc'),
      borderRadius: 6,
    }],
  };

  const barOpts = {
    responsive: true,
    plugins: { legend: { labels: { color: '#8b9fc9' } } },
    scales: {
      x: { ticks: { color: '#8b9fc9' }, grid: { display: false } },
      y: { ticks: { color: '#8b9fc9' }, grid: { color: 'rgba(99,130,201,0.1)' } },
    },
  };

  return (
    <div className="animate-in">
      <div className="grid-2">
        <div className="card">
          <h3 style={{ marginBottom: 16 }}>Monthly Cost by Scenario</h3>
          <div className="chart-wrap">
            <Bar data={costData} options={barOpts} />
          </div>
        </div>
        <div className="card">
          <h3 style={{ marginBottom: 16 }}>Required Instances by Scenario</h3>
          <div className="chart-wrap">
            <Bar data={instanceData} options={barOpts} />
          </div>
        </div>
      </div>

      <div className="card mt-24">
        <h3 style={{ marginBottom: 16 }}>Scenario Comparison Table</h3>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Metric</th>
                {scenarioNames.map(n => <th key={n}>{n.charAt(0).toUpperCase() + n.slice(1)}</th>)}
              </tr>
            </thead>
            <tbody>
              {['total_monthly_cost', 'annual_cost', 'required_instances', 'compute_cost', 'storage_cost', 'availability_overhead_pct'].map(metric => (
                <tr key={metric}>
                  <td className="text-sm font-mono" style={{ color: 'var(--accent-2)' }}>{metric.replace(/_/g, ' ')}</td>
                  {scenarioNames.map(n => {
                    const val = scenarios[n]?.[metric];
                    return (
                      <td key={n} className="text-sm font-mono">
                        {typeof val === 'number'
                          ? metric.includes('cost') || metric.includes('annual') ? `$${val.toLocaleString()}` : `${val.toLocaleString()}${metric.includes('pct') ? '%' : ''}`
                          : '—'}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {scenarioNames.some(n => scenarios[n]?.constraint_violations?.length > 0) && (
        <div className="card mt-24">
          <h3 style={{ marginBottom: 12 }}>Constraint Violations</h3>
          {scenarioNames.map(n => (
            scenarios[n]?.constraint_violations?.length > 0 && (
              <div key={n} className="mb-8">
                <strong>{n}:</strong>
                {scenarios[n].constraint_violations.map((v, i) => (
                  <div key={i} className="alert alert-warning mt-8">{v}</div>
                ))}
              </div>
            )
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main SimulationResults component ────────────────────────────────────────
export default function SimulationResults({ results, seed }) {
  const [activeTab, setActiveTab] = useState('results');
  const simResult = results?.simulation_result || {};
  const method = simResult?.method || results?.simulation_method || 'unknown';
  const riskNotes = results?.risk_notes || [];
  const explanation = results?.explanation || '';
  const assumptions = results?.assumptions || [];
  const stepLog = results?.step_log || [];

  return (
    <div className="animate-in">
      <div className="tab-bar mb-16">
        {['results', 'explanation', 'assumptions', 'methodology'].map(tab => (
          <button
            key={tab}
            id={`result-tab-${tab}`}
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {activeTab === 'results' && (
        <div>
          <div className="flex justify-between items-center mb-16">
            <div>
              <span className="badge badge-info" style={{ marginRight: 8 }}>Method: {method.replace('_', ' ')}</span>
              <span className="badge badge-muted">Seed: {seed}</span>
            </div>
          </div>

          {riskNotes.length > 0 && (
            <div className="card mb-24">
              <h3 style={{ marginBottom: 12 }}>🔍 Risk Observations</h3>
              {riskNotes.map((note, i) => (
                <div key={i} className={`alert ${note.startsWith('WARNING') ? 'alert-warning' : 'alert-info'} mb-8`}>
                  {note}
                </div>
              ))}
            </div>
          )}

          {method === 'sensitivity' && <SensitivityView result={simResult} />}
          {method === 'monte_carlo' && <MonteCarloView result={simResult} />}
          {method === 'scenario_comparison' && <ScenarioComparisonView result={simResult} />}

          {results?.errors?.length > 0 && (
            <div className="card mt-24">
              <h3 style={{ marginBottom: 12 }}>Errors</h3>
              {results.errors.map((e, i) => (
                <div key={i} className="alert alert-danger mb-8">{e}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'explanation' && (
        <div className="card">
          <h3 style={{ marginBottom: 16 }}>Decision Explanation</h3>
          {explanation ? (
            <div className="explanation-text" style={{ fontSize: '0.9rem', lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
              {explanation}
            </div>
          ) : (
            <p className="text-muted">No explanation generated (Ollama may not be running).</p>
          )}
        </div>
      )}

      {activeTab === 'assumptions' && (
        <AssumptionsPanel assumptions={assumptions} />
      )}

      {activeTab === 'methodology' && (
        <div>
          <div className="card mb-16">
            <h3 style={{ marginBottom: 12 }}>Agent Execution Log</h3>
            <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem', lineHeight: 1.7 }}>
              {stepLog.map((s, i) => (
                <div key={i} style={{ color: s.includes('error') || s.includes('fail') ? 'var(--accent-danger)' : 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{String(i + 1).padStart(2, '0')}</span> {s}
                </div>
              ))}
            </div>
          </div>
          <div className="card">
            <h3 style={{ marginBottom: 12 }}>Methodology Notes</h3>
            <div className="alert alert-info">
              Engine version: {simResult?.engine_version || '1.0.0'} ·
              Elapsed: {simResult?.elapsed_seconds?.toFixed(3) || '?'}s ·
              Seed: {seed}
            </div>
            <p style={{ fontSize: '0.85rem', marginTop: 12 }}>
              See <code>docs/simulation_methodology.md</code> for full equation documentation.
              All calculations use deterministic Python — no LLM-generated code is ever executed.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
