/**
 * Voice-narration toggle for the review tour (REVIEW-009). Mirrors the
 * SoundToggle chip so the two read as one family, and disappears completely on
 * browsers with no speech engine — a toggle that can only ever be inert is
 * worse than no toggle.
 */
import { useEffect, useState } from 'react';
import { Mic, MicOff } from 'lucide-react';

import { getPref, setPref, subscribePrefs } from '../lib/settings';
import { stopSpeaking, voiceAvailable } from '../lib/voice';

export default function VoiceToggle() {
  const [voice, setVoice] = useState(() => getPref('voice'));
  const [available] = useState(() => voiceAvailable());

  useEffect(() => subscribePrefs((p) => setVoice(p.voice)), []);

  if (!available) return null;

  function toggle() {
    const next = !voice;
    setPref('voice', next);
    // Switching off must also silence a sentence already in mid-air.
    if (!next) stopSpeaking();
  }

  return (
    <button
      type="button"
      className={`toggle-chip${voice ? ' on' : ''}`}
      aria-pressed={voice}
      onClick={toggle}
      title={voice ? 'The narrator is speaking each move' : 'The narrator is silent'}
    >
      {voice ? <Mic size={14} aria-hidden="true" /> : <MicOff size={14} aria-hidden="true" />}
      {voice ? 'Voice on' : 'Voice off'}
    </button>
  );
}
