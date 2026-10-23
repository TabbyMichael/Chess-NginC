/**
 * Theme context object and its shape, kept separate from the provider so
 * both `theme.tsx` (component) and `useTheme.ts` (hook) can import it
 * without breaking React Fast Refresh.
 */
import { createContext } from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';

export type ThemeContextValue = {
  preference: ThemePreference;
  resolved: 'light' | 'dark';
  setPreference: (preference: ThemePreference) => void;
};

export const ThemeContext = createContext<ThemeContextValue | null>(null);
