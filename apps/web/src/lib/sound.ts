/**
 * Synthesized game sounds (WebAudio, no asset files). Every event maps to a
 * short tone cluster whose volume/complexity scales with an intensity level so
 * a quiet pawn push feels different from checkmate. Fully guarded: in jsdom
 * (tests) or browsers without WebAudio the calls are inert no-ops.
 */

export type SoundName =
  | 'select'
  | 'move'
  | 'castle'
  | 'capture'
  | 'promotion'
  | 'check'
  | 'checkmate'
  | 'gameEnd'
  | 'error'
  | 'achievement';

type Tone = { freq: number; dur: number; gain: number; type?: OscillatorType; delay?: number };

// Base presets at intensity 1; `playSound` scales gain with the intensity arg.
const PRESETS: Record<SoundName, Tone[]> = {
  // Barely-there tick when picking up a piece.
  select: [{ freq: 320, dur: 0.03, gain: 0.05, type: 'triangle' }],
  // Soft wooden thud for a quiet move.
  move: [{ freq: 180, dur: 0.06, gain: 0.12, type: 'triangle' }],
  // Two-note clop: rook shifts, then the king lands.
  castle: [
    { freq: 200, dur: 0.05, gain: 0.14, type: 'triangle' },
    { freq: 160, dur: 0.06, gain: 0.14, type: 'triangle', delay: 0.09 },
  ],
  // Sharper, brighter crack for a capture.
  capture: [
    { freq: 260, dur: 0.05, gain: 0.18, type: 'square' },
    { freq: 140, dur: 0.07, gain: 0.14, type: 'triangle', delay: 0.02 },
  ],
  // Rising shimmer for a promotion.
  promotion: [
    { freq: 420, dur: 0.06, gain: 0.14, type: 'triangle' },
    { freq: 560, dur: 0.06, gain: 0.14, type: 'triangle', delay: 0.06 },
    { freq: 720, dur: 0.09, gain: 0.14, type: 'triangle', delay: 0.12 },
  ],
  // Bright alert ding for a check.
  check: [
    { freq: 660, dur: 0.09, gain: 0.18, type: 'sine' },
    { freq: 880, dur: 0.12, gain: 0.14, type: 'sine', delay: 0.02 },
  ],
  // Deep resolving chord for checkmate.
  checkmate: [
    { freq: 523, dur: 0.18, gain: 0.2, type: 'sine' },
    { freq: 659, dur: 0.18, gain: 0.18, type: 'sine', delay: 0.02 },
    { freq: 784, dur: 0.28, gain: 0.2, type: 'sine', delay: 0.04 },
  ],
  // Neutral descending cadence for a non-mate finish (resign/draw/stalemate).
  gameEnd: [
    { freq: 440, dur: 0.14, gain: 0.16, type: 'sine' },
    { freq: 330, dur: 0.2, gain: 0.16, type: 'sine', delay: 0.1 },
  ],
  // Low buzz for a rejected/illegal move.
  error: [
    { freq: 150, dur: 0.1, gain: 0.16, type: 'sawtooth' },
    { freq: 110, dur: 0.12, gain: 0.14, type: 'sawtooth', delay: 0.02 },
  ],
  // Celebratory fanfare for an unlocked achievement.
  achievement: [
    { freq: 523, dur: 0.1, gain: 0.16, type: 'triangle' },
    { freq: 659, dur: 0.1, gain: 0.16, type: 'triangle', delay: 0.1 },
    { freq: 784, dur: 0.1, gain: 0.16, type: 'triangle', delay: 0.2 },
    { freq: 1046, dur: 0.22, gain: 0.18, type: 'triangle', delay: 0.3 },
  ],
};

let ctx: AudioContext | null = null;

function audioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  const Ctor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!ctx) {
    try {
      ctx = new Ctor();
    } catch {
      return null;
    }
  }
  return ctx;
}

function playTone(c: AudioContext, tone: Tone, gainScale: number): void {
  const osc = c.createOscillator();
  const gain = c.createGain();
  osc.type = tone.type ?? 'sine';
  osc.frequency.value = tone.freq;
  const peak = Math.min(0.5, tone.gain * gainScale);
  const start = c.currentTime + (tone.delay ?? 0);
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(peak, start + 0.008);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + tone.dur);
  osc.connect(gain);
  gain.connect(c.destination);
  osc.start(start);
  osc.stop(start + tone.dur + 0.03);
}

/**
 * Play a named sound. `intensity` (0..1) scales volume so the same event can
 * land softly or with weight (e.g. captures of bigger pieces play louder).
 */
export function playSound(name: SoundName, intensity = 0.6): void {
  const c = audioContext();
  if (!c) return;
  // Autoplay policy: resume on the first gesture-driven call.
  if (c.state === 'suspended') {
    void c.resume().catch(() => {});
  }
  const scale = 0.5 + Math.max(0, Math.min(1, intensity));
  for (const tone of PRESETS[name]) {
    try {
      playTone(c, tone, scale);
    } catch {
      /* a single failed oscillator must not break the game */
    }
  }
}
