/**
 * Auth context object and its shape, kept separate from the provider so both
 * `AuthContext.tsx` (component) and `useAuth.ts` (hook) can import it without
 * breaking React Fast Refresh.
 */
import { createContext } from 'react';

import type { UserResponse } from '../lib/api-types';

export type AuthState = {
  user: UserResponse | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
};

export const AuthContext = createContext<AuthState | null>(null);
