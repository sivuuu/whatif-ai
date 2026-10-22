import React, { useEffect, useState } from 'react';
import api from '../api/client';
import SimulationResults from '../components/SimulationResults';

export default function History() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [runDetail, setRunDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    api.listRuns()
      .then(data => setRuns(data.results || data || []))
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, []);

  async function loadDetail(run) {
    setSelected(run.id);
    setLoadingDetail(true);
    try {
      const detail = await api.getRun(run.id);
      setRunDetail(detail);
    } catch (e) {
      setRunDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }

  return (
    <div className="animate-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Run History</h1>
          <p className="page-subtitle">All simulation runs with reproducibility metadata</p>
        </div>
      </div>

      {loading && <div className="loading-center"><div className="spinner" /><span>Loading runs…</span></div>}

      {!loading && runs.length === 0 && (
        <div className="alert alert-info">No simulation runs yet. Run a scenario from the Workspace.</div>
      )}

      {!loading && runs.length > 0 && (
        <div className="grid-2">
          <div>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Method</th>
                    <th>Status</th>
                    <th>Seed</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map(run => (
                    <tr
                      key={run.id}
                      onClick={() => loadDetail(run)}
                      style={{ cursor: 'pointer', background: selected === run.id ? 'var(--bg-elevated)' : undefined }}
                    >
                      <td className="text-sm font-mono">#{run.id}</td>
                      <td className="text-sm">{run.config?.method || '—'}</td>
                      <td>
                        <span className={`badge badge-${run.status === 'completed' ? 'success' : run.status === 'failed' ? 'danger' : 'info'}`}>
                          {run.status}
                        </span>
                      </td>
                      <td className="font-mono text-sm">{run.seed}</td>
                      <td className="text-xs text-muted">{new Date(run.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            {loadingDetail && <div className="loading-center"><div className="spinner" /></div>}
            {runDetail && !loadingDetail && (
              <div className="card">
                <h3 style={{ marginBottom: 12 }}>Run #{runDetail.id} — {runDetail.config?.method}</h3>
                <div className="flex gap-8 mb-16" style={{ flexWrap: 'wrap' }}>
                  <span className="badge badge-muted">Seed: {runDetail.seed}</span>
                  <span className="badge badge-muted">v{runDetail.algorithm_version}</span>
                  <span className={`badge badge-${runDetail.status === 'completed' ? 'success' : 'danger'}`}>{runDetail.status}</span>
                </div>
                {runDetail.result && (
                  <div>
                    <h4 style={{ marginBottom: 8 }}>Summary</h4>
                    <div className="table-wrapper">
                      <table>
                        <tbody>
                          {Object.entries(runDetail.result?.summary || {}).slice(0, 8).map(([k, v]) => (
                            <tr key={k}>
                              <td className="text-sm font-mono" style={{ color: 'var(--accent-2)' }}>{k}</td>
                              <td className="text-sm">{typeof v === 'number' ? v.toLocaleString() : JSON.stringify(v)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
