import React, { createContext, useContext, useState, useCallback } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const u = localStorage.getItem('whatif_user');
    return u ? JSON.parse(u) : null;
  });

  const login = useCallback(async (username, password) => {
    const data = await api.login({ username, password });
    localStorage.setItem('whatif_token', data.token);
    localStorage.setItem('whatif_user', JSON.stringify({ username: data.username, id: data.user_id }));
    setUser({ username: data.username, id: data.user_id });
    return data;
  }, []);

  const register = useCallback(async (username, password, email) => {
    const data = await api.register({ username, password, email });
    localStorage.setItem('whatif_token', data.token);
    localStorage.setItem('whatif_user', JSON.stringify({ username: data.username, id: data.user_id }));
    setUser({ username: data.username, id: data.user_id });
    return data;
  }, []);

  const logout = useCallback(async () => {
    try { await api.logout(); } catch (e) {}
    localStorage.removeItem('whatif_token');
    localStorage.removeItem('whatif_user');
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
