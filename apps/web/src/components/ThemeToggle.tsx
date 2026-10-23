/**
 * Accessible theme switcher: cycles Light → Dark → System.
 * Preference persists via ThemeProvider (localStorage).
 */
import { Monitor, Moon, Sun } from 'lucide-react';

import { useTheme } from '../app/useTheme';

const NEXT_LABEL: Record<string, string> = {
  light: 'Switch to dark theme',
  dark: 'Switch to system theme',
  system: 'Switch to light theme',
};

export default function ThemeToggle() {
  const { preference, setPreference } = useTheme();
  const Icon = preference === 'light' ? Sun : preference === 'dark' ? Moon : Monitor;

  function cycle() {
    const order = ['light', 'dark', 'system'] as const;
    const next = order[(order.indexOf(preference) + 1) % order.length];
    setPreference(next);
  }

  return (
    <button
      type="button"
      className="icon-btn"
      onClick={cycle}
      aria-label={NEXT_LABEL[preference]}
      title={`${NEXT_LABEL[preference]} (current: ${preference})`}
    >
      <Icon size={16} aria-hidden="true" />
    </button>
  );
}
