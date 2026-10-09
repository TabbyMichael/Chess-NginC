/**
 * Auth hook kept in its own module so `AuthContext.tsx` exports only a
 * component — required for React Fast Refresh to work in development.
 */
import { useContext } from 'react';

import { AuthContext, type AuthState } from './auth-context';

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
