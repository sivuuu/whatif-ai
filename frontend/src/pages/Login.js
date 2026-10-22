import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login({ onSwitch }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(username, password);
      } else {
        await register(username, password, email);
      }
      if (onSwitch) onSwitch();
      navigate('/');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-base)',
      padding: 24,
    }}>
      <div style={{ width: '100%', maxWidth: 400 }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 56, height: 56,
            background: 'linear-gradient(135deg, var(--accent), var(--accent-2))',
            borderRadius: 16,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 28, margin: '0 auto 16px',
          }}>🤔</div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>WhatIf AI</h1>
          <p className="text-muted">Decision Intelligence Simulator</p>
        </div>

        <div className="card-glass" style={{ borderRadius: 'var(--radius-lg)', padding: 32 }}>
          <div className="tab-bar mb-24" style={{ background: 'var(--bg-base)' }}>
            <button className={`tab-btn ${mode === 'login' ? 'active' : ''}`} onClick={() => setMode('login')}>Sign In</button>
            <button className={`tab-btn ${mode === 'register' ? 'active' : ''}`} onClick={() => setMode('register')}>Register</button>
          </div>

          {error && <div className="alert alert-danger mb-16">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Username</label>
              <input
                id="login-username"
                className="form-input"
                type="text"
                placeholder="Username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
              />
            </div>
            {mode === 'register' && (
              <div className="form-group">
                <label className="form-label">Email (optional)</label>
                <input
                  id="register-email"
                  className="form-input"
                  type="email"
                  placeholder="email@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                />
              </div>
            )}
            <div className="form-group">
              <label className="form-label">Password</label>
              <input
                id="login-password"
                className="form-input"
                type="password"
                placeholder="Password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
            </div>
            <button id="auth-submit-btn" className="btn btn-primary w-full" type="submit" disabled={loading}>
              {loading ? '⏳ Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          <div className="mt-16 text-center">
            <button
              className="btn btn-secondary w-full"
              onClick={() => {
                if (onSwitch) onSwitch();
                navigate('/');
              }}
              style={{ fontSize: '0.8rem' }}
            >
              Continue without account (demo mode)
            </button>
          </div>

          <div className="alert alert-info mt-16" style={{ fontSize: '0.75rem' }}>
            💡 Demo credentials: <strong>demo</strong> / <strong>whatif2024</strong> (after running seed_data)
          </div>
        </div>
      </div>
    </div>
  );
}
