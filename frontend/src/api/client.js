// WhatIf AI – API client
const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

function getToken() {
  return localStorage.getItem('whatif_token');
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Token ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.error || JSON.stringify(err));
  }

  // 204 No Content
  if (res.status === 204) return null;
  return res.json();
}

// Auth
export const api = {
  login: (data) => request('/auth/login/', { method: 'POST', body: JSON.stringify(data) }),
  register: (data) => request('/auth/register/', { method: 'POST', body: JSON.stringify(data) }),
  logout: () => request('/auth/logout/', { method: 'POST' }),

  // Dashboard
  stats: () => request('/stats/'),

  // Quick-run (no auth required)
  quickRun: (raw_input, seed = 42) =>
    request('/quick-run/', { method: 'POST', body: JSON.stringify({ raw_input, seed }) }),

  // Scenarios
  interpretScenario: (raw_input, seed = 42) =>
    request('/scenarios/interpret/', { method: 'POST', body: JSON.stringify({ raw_input, seed }) }),

  listScenarios: (project_id) =>
    request(`/scenarios/${project_id ? `?project=${project_id}` : ''}`),

  createScenario: (data) =>
    request('/scenarios/', { method: 'POST', body: JSON.stringify(data) }),

  updateScenario: (id, data) =>
    request(`/scenarios/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),

  deleteScenario: (id) =>
    request(`/scenarios/${id}/`, { method: 'DELETE' }),

  validateScenario: (id) =>
    request(`/scenarios/${id}/validate/`, { method: 'POST' }),

  // Simulation runs
  launchRun: (data) =>
    request('/runs/launch/', { method: 'POST', body: JSON.stringify(data) }),

  listRuns: () => request('/runs/'),

  getRun: (id) => request(`/runs/${id}/`),

  compareRuns: (id, other_id) =>
    request(`/runs/${id}/compare/?other=${other_id}`),

  exportReport: (run_id) =>
    request(`/runs/${run_id}/export_report/`, { method: 'POST' }),

  // Projects
  listProjects: () => request('/projects/'),
  createProject: (data) =>
    request('/projects/', { method: 'POST', body: JSON.stringify(data) }),
};

export default api;
