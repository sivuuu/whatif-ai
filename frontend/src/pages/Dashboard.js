import React, { useEffect, useState } from 'react';
import api from '../api/client';

function StatCard({ label, value, icon, color = 'accent' }) {
  return (
    <div className="stat-card animate-in">
      <span className="stat-icon">{icon}</span>
      <div className="stat-value" style={{ color: `var(--${color})` }}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.stats()
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="loading-center">
      <div className="spinner" />
      <span>Loading dashboard…</span>
    </div>
  );

  if (error) return (
    <div className="alert alert-danger">⚠ {error}. Is the backend running on port 8000?</div>
  );

  return (
    <div className="animate-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Overview</h1>
          <p className="page-subtitle">WhatIf AI — Enterprise Decision Intelligence Simulator</p>
        </div>
      </div>

      <div className="stat-grid">
        <StatCard label="Total Scenarios" value={stats?.total_scenarios ?? 0} icon="📋" />
        <StatCard label="Simulation Runs" value={stats?.total_runs ?? 0} icon="⚙️" />
        <StatCard label="Completed" value={stats?.completed_runs ?? 0} icon="✅" color="accent-3" />
        <StatCard label="Failed" value={stats?.failed_runs ?? 0} icon="❌" color="accent-danger" />
      </div>

      <div className="grid-2">
        <div className="card">
          <h3 style={{ marginBottom: 16 }}>Recent Scenarios</h3>
          {stats?.recent_scenarios?.length === 0 && (
            <p className="text-muted text-sm">No scenarios yet. Create your first one →</p>
          )}
          {stats?.recent_scenarios?.map(s => (
            <div key={s.id} className="card-elevated mb-8" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{s.title}</div>
                <div className="text-xs text-muted mt-4">{s.domain} · {s.status}</div>
              </div>
              <span className={`badge badge-${s.status === 'validated' ? 'success' : s.status === 'needs_clarification' ? 'warning' : 'muted'}`}>
                {s.status}
              </span>
            </div>
          ))}
        </div>

        <div className="card">
          <h3 style={{ marginBottom: 16 }}>Recent Runs</h3>
          {stats?.recent_runs?.length === 0 && (
            <p className="text-muted text-sm">No simulation runs yet.</p>
          )}
          {stats?.recent_runs?.map(r => (
            <div key={r.id} className="card-elevated mb-8" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Run #{r.id}</div>
                <div className="text-xs text-muted mt-4">{r.algorithm_version} · seed {r.seed}</div>
              </div>
              <span className={`badge badge-${r.status === 'completed' ? 'success' : r.status === 'failed' ? 'danger' : 'info'}`}>
                {r.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="card mt-24">
        <h3 style={{ marginBottom: 8 }}>Quick Start</h3>
        <p style={{ marginBottom: 16 }}>
          Describe a hypothetical operational scenario in plain English. WhatIf AI will extract
          variables, run a simulation, and explain the results with traceable assumptions.
        </p>
        <div className="alert alert-info">
          💡 Example: <em>"What if monthly cloud costs rise by 20%, user traffic doubles, and we need to maintain 99.9% availability?"</em>
          — head to the <strong>Workspace</strong> to try it.
        </div>
      </div>
    </div>
  );
}
