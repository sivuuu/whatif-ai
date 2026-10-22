import React from 'react';

const DIST_OPTIONS = ['fixed', 'normal', 'uniform', 'triangular', 'lognormal'];

const VAR_META = {
  base_monthly_cost: { label: 'Base Monthly Cost', icon: '💵' },
  cost_increase_pct: { label: 'Cost Increase', icon: '📈' },
  traffic_multiplier: { label: 'Traffic Multiplier', icon: '🌐' },
  availability_target: { label: 'Availability Target', icon: '⏱' },
  current_instances: { label: 'Current Instances', icon: '🖥' },
  instance_cost_per_hr: { label: 'Instance Cost/hr', icon: '💰' },
  storage_gb: { label: 'Storage', icon: '💾' },
  storage_cost_per_gb: { label: 'Storage Cost/GB', icon: '📦' },
  data_transfer_gb: { label: 'Data Transfer', icon: '📡' },
  transfer_cost_per_gb: { label: 'Transfer Cost/GB', icon: '🔄' },
};

export default function VariableEditor({ variables = {}, onChange }) {
  return (
    <div>
      <div className="var-row" style={{ borderBottom: '1px solid var(--border)', paddingBottom: 8, marginBottom: 8 }}>
        <span className="text-xs text-muted">Variable</span>
        <span className="text-xs text-muted">Value</span>
        <span className="text-xs text-muted">Unit</span>
        <span className="text-xs text-muted">Distribution</span>
      </div>
      {Object.entries(variables).map(([varName, varDef]) => {
        const meta = VAR_META[varName] || { label: varName, icon: '📊' };
        const val = typeof varDef === 'object' ? varDef : { value: varDef };
        return (
          <div key={varName} className="var-row animate-in">
            <div>
              <div style={{ fontWeight: 500, fontSize: '0.8rem' }}>{meta.icon} {meta.label}</div>
              <div className="var-name">{varName}</div>
            </div>
            <input
              id={`var-${varName}-value`}
              className="form-input"
              type="number"
              step="any"
              value={val.value ?? ''}
              onChange={e => onChange(varName, 'value', e.target.value)}
            />
            <span className="text-sm text-muted">{val.unit || '—'}</span>
            <select
              id={`var-${varName}-dist`}
              className="form-select"
              value={val.dist || 'fixed'}
              onChange={e => onChange(varName, 'dist', e.target.value)}
            >
              {DIST_OPTIONS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
        );
      })}
    </div>
  );
}
