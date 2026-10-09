/**
 * Auth state: session restoration (WEB-008), login/register/logout.
 * Backend owns the session cookie; this context caches the user profile.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { AuthContext } from './auth-context';
import { ApiError, api } from '../lib/api-client';
import type { UserResponse } from '../lib/api-types';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Session restoration on mount (WEB-008).
  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch((err: unknown) => {
        if (!cancelled && err instanceof ApiError && err.status !== 401) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      setUser(await api.login({ email, password }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed');
      throw err;
    }
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      setUser(await api.register({ email, password }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Registration failed');
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo(
    () => ({ user, loading, error, login, register, logout, clearError }),
    [user, loading, error, login, register, logout, clearError],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
