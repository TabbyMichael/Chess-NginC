/**
 * Spoken narration for the review tour (REVIEW-009), on the browser's own
 * speech engine. Free in every sense: the voices come with the OS, there is no
 * asset download, no API key and no network call.
 *
 * Fully guarded like `lib/sound.ts` — in jsdom, or any browser without
 * `speechSynthesis`, every function here is an inert no-op rather than a throw.
 */

// A calm, authoritative read: slightly slower than the default and a touch
// below the default pitch. Composed narration sounds rushed at rate 1.
const VOICE_RATE = 0.92;
const VOICE_PITCH = 0.92;
const VOICE_VOLUME = 1;

// Chrome silently abandons an utterance after roughly 15 seconds of speech; a
// rate-0.92 voice gets through something like 180 characters in that window, so
// narration is chunked well inside it.
const MAX_CHUNK = 180;

// Preference order, not a claim that these exist everywhere: English
// narration/documentary voices tend to be the composed ones, and the platform's
// own voice list is the only authority on which are installed.
const VOICE_HINTS = [
  'Daniel',
  'Google UK English Male',
  'Arthur',
  'Oliver',
  'Microsoft George',
  'David',
  'Google US English',
];

function engine(): SpeechSynthesis | null {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null;
  if (typeof window.SpeechSynthesisUtterance !== 'function') return null;
  return window.speechSynthesis;
}

/** Whether this browser can narrate at all; the UI hides the toggle if not. */
export function voiceAvailable(): boolean {
  return engine() !== null;
}

/**
 * Resolve the calm voice for one utterance.
 *
 * Resolved per call rather than cached: Chrome reports an empty list until
 * `voiceschanged` fires, and since every step of the tour re-asks, a listener
 * would only ever arrive at the same answer one step later. No state, same
 * outcome — at worst the very first sentence uses the platform default.
 */
function pickVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  if (voices.length === 0) return null;
  for (const hint of VOICE_HINTS) {
    const match = voices.find((voice) => voice.name.toLowerCase().includes(hint.toLowerCase()));
    if (match) return match;
  }
  return (
    voices.find((voice) => voice.lang?.startsWith('en-GB')) ??
    voices.find((voice) => voice.lang?.startsWith('en')) ??
    voices.find((voice) => voice.default) ??
    null
  );
}

/**
 * Split narration into speakable chunks, breaking between sentences whenever
 * one fits. Splitting on punctuation alone would tear "1.5 pawns" in two, so
 * this walks words and only closes a chunk on sentence-final punctuation.
 */
export function chunkText(text: string, max = MAX_CHUNK): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const chunks: string[] = [];
  let current = '';
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (current && candidate.length > max) {
      chunks.push(current);
      current = word;
      continue;
    }
    current = candidate;
    if (current.length >= max * 0.6 && /[.!?]$/.test(current)) {
      chunks.push(current);
      current = '';
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

/**
 * Speak `text`, replacing anything already saying.
 *
 * Cancelling first is what makes stepping quickly through a game feel
 * responsive instead of queuing a backlog of stale commentary.
 */
export function speak(text: string): void {
  const synth = engine();
  const trimmed = text.trim();
  if (!synth || !trimmed) return;
  try {
    synth.cancel();
    const voice = pickVoice(synth.getVoices());
    for (const chunk of chunkText(trimmed)) {
      const utterance = new SpeechSynthesisUtterance(chunk);
      utterance.rate = VOICE_RATE;
      utterance.pitch = VOICE_PITCH;
      utterance.volume = VOICE_VOLUME;
      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
      }
      // Aborted/blocked speech is normal during fast navigation: stay silent.
      utterance.onerror = () => {};
      synth.speak(utterance);
    }
  } catch {
    /* narration is an enhancement; it must never break the review page */
  }
}

/** Silence the narrator (called when the page unmounts or voice is switched off). */
export function stopSpeaking(): void {
  try {
    engine()?.cancel();
  } catch {
    /* nothing to stop */
  }
}
