import React from 'react';
import { BrowserRouter, Routes, Route, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Dashboard from './pages/Dashboard';
import Workspace from './pages/Workspace';
import History from './pages/History';
import Login from './pages/Login';

function AppLayout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // If on login page, display full-screen without sidebar/topbar chrome
  if (location.pathname === '/login') {
    return <>{children}</>;
  }

  return (
    <div className="app-shell">
      {/* Top Navigation Bar */}
      <header className="topbar">
        <NavLink to="/" className="topbar-brand">
          <div className="topbar-brand-icon">🤔</div>
          <span>WhatIf AI</span>
        </NavLink>
        <span className="topbar-badge">v1.0 Decision Engine</span>

        <div className="topbar-spacer" />

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            id="nav-quick-workspace"
            className="btn btn-primary btn-sm"
            onClick={() => navigate('/workspace')}
          >
            + New Scenario
          </button>

          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '4px 10px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-elevated)',
                  fontSize: '0.8125rem',
                }}
              >
                <span>👤</span>
                <span style={{ fontWeight: 600 }}>{user.username}</span>
              </div>
              <button
                id="btn-logout"
                className="btn btn-secondary btn-sm"
                onClick={logout}
              >
                Sign Out
              </button>
            </div>
          ) : (
            <NavLink to="/login" className="btn btn-secondary btn-sm">
              Sign In
            </NavLink>
          )}
        </div>
      </header>

      {/* Left Sidebar */}
      <aside className="sidebar">
        <div className="nav-section-label">Navigation</div>
        <NavLink
          to="/"
          id="nav-overview"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          end
        >
          <span className="nav-link-icon">📊</span>
          <span>Overview</span>
        </NavLink>
        <NavLink
          to="/workspace"
          id="nav-workspace"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <span className="nav-link-icon">⚡</span>
          <span>Workspace</span>
        </NavLink>
        <NavLink
          to="/history"
          id="nav-history"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <span className="nav-link-icon">📜</span>
          <span>Run History</span>
        </NavLink>

        <div className="nav-section-label" style={{ marginTop: 24 }}>System</div>
        <div
          style={{
            padding: '10px 12px',
            background: 'var(--bg-elevated)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border)',
            fontSize: '0.75rem',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--success)' }} />
          <span className="text-muted">Engine: Online (Port 8000)</span>
        </div>

        <div style={{ marginTop: 'auto', paddingTop: 20 }}>
          <div className="text-xs text-muted" style={{ padding: '0 12px' }}>
            WhatIf AI &copy; 2026<br />
            Reproducible Scenario Intelligence
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/workspace" element={<Workspace />} />
            <Route path="/history" element={<History />} />
            <Route path="/login" element={<Login />} />
            <Route path="*" element={<Dashboard />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
