/**
 * User UX preferences (sound + haptics), persisted in localStorage.
 * Kept framework-free so the audio/haptic layers and the React toggles share
 * one source of truth. A `change` event lets components re-render on toggle.
 */

export type PrefKey = 'sound' | 'haptics';

const STORAGE_KEY = 'chess.preferences';
const CHANGE_EVENT = 'chess:preferences';

type Prefs = { sound: boolean; haptics: boolean };

const DEFAULTS: Prefs = { sound: true, haptics: true };

function read(): Prefs {
  if (typeof localStorage === 'undefined') return { ...DEFAULTS };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Prefs>) };
  } catch {
    return { ...DEFAULTS };
  }
}

function write(next: Prefs): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* storage full or blocked: preferences just don't persist */
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: next }));
  }
}

export function getPref(key: PrefKey): boolean {
  return read()[key];
}

export function setPref(key: PrefKey, value: boolean): void {
  const next = read();
  next[key] = value;
  write(next);
}

export function allPrefs(): Prefs {
  return read();
}

/** Subscribe to preference changes; returns an unsubscribe fn. */
export function subscribePrefs(fn: (p: Prefs) => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const handler = (e: Event) => fn((e as CustomEvent<Prefs>).detail);
  window.addEventListener(CHANGE_EVENT, handler);
  return () => window.removeEventListener(CHANGE_EVENT, handler);
}
