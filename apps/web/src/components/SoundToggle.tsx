/**
 * Sound & haptics toggles for the game pages. Persisted via the preferences
 * store so the choice carries across games and reloads. Buttons announce their
 * state for screen readers and are labelled for tests.
 */
import { useEffect, useState } from 'react';
import { Smartphone, Volume2, VolumeX } from 'lucide-react';

import { getPref, setPref, subscribePrefs, type PrefKey } from '../lib/settings';

function usePref(key: PrefKey): [boolean, (v: boolean) => void] {
  const [value, setValue] = useState(() => getPref(key));
  useEffect(() => subscribePrefs((p) => setValue(p[key])), [key]);
  return [value, (v: boolean) => setPref(key, v)];
}

export default function SoundToggle() {
  const [sound, setSound] = usePref('sound');
  const [haptics, setHaptics] = usePref('haptics');

  return (
    <div className="sound-toggle" role="group" aria-label="game feedback settings">
      <button
        type="button"
        className={`toggle-chip${sound ? ' on' : ''}`}
        aria-pressed={sound}
        onClick={() => setSound(!sound)}
        title={sound ? 'Sounds are on' : 'Sounds are off'}
      >
        {sound ? (
          <Volume2 size={15} aria-hidden="true" />
        ) : (
          <VolumeX size={15} aria-hidden="true" />
        )}
        {sound ? 'Sound on' : 'Sound off'}
      </button>
      <button
        type="button"
        className={`toggle-chip${haptics ? ' on' : ''}`}
        aria-pressed={haptics}
        onClick={() => setHaptics(!haptics)}
        title={haptics ? 'Vibration is on' : 'Vibration is off'}
      >
        <Smartphone size={15} aria-hidden="true" />
        {haptics ? 'Haptics on' : 'Haptics off'}
      </button>
    </div>
  );
}
