import React from 'react';

const CONFIDENCE_COLORS = {
  high: 'success',
  medium: 'warning',
  low: 'danger',
};

export default function AssumptionsPanel({ assumptions = [] }) {
  return (
    <div className="card">
      <h3 style={{ marginBottom: 12 }}>Assumptions</h3>
      {assumptions.length === 0 && (
        <p className="text-sm text-muted">No assumptions captured yet.</p>
      )}
      {assumptions.map((a, i) => (
        <div key={i} className="assumption-item animate-in">
          <span className={`badge badge-${CONFIDENCE_COLORS[a.confidence] || 'muted'} assumption-confidence`}>
            {a.confidence || 'unknown'}
          </span>
          <div>
            <div style={{ fontSize: '0.85rem' }}>{a.text}</div>
            <div className="text-xs text-muted mt-4">Source: {a.source || 'model'}</div>
          </div>
        </div>
      ))}
      <div className="alert alert-info mt-16" style={{ fontSize: '0.75rem' }}>
        All assumptions are documented and traceable. Validate against your actual data before
        using results for real decisions.
      </div>
    </div>
  );
}
