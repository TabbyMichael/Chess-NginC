/**
 * Voice narration tests (REVIEW-009). jsdom ships no speech engine, which is
 * exactly the condition the module must survive, so every test installs — or
 * withholds — its own fake and asserts on the calls it receives.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import { chunkText, speak, stopSpeaking, voiceAvailable } from './voice';

type FakeVoice = { name: string; lang: string; default?: boolean };

/** Utterances the fake engine recorded, in the order it was asked to say them. */
let spoken: string[];
let cancel: ReturnType<typeof vi.fn>;

function installSpeech(voices: FakeVoice[] = []) {
  spoken = [];
  cancel = vi.fn();
  const speakSpy = vi.fn();
  Object.defineProperty(window, 'speechSynthesis', {
    configurable: true,
    value: {
      cancel,
      speak: (utterance: { text: string; voice?: FakeVoice }) => {
        spoken.push(utterance.text);
        speakSpy(utterance);
      },
      getVoices: () => voices,
    },
  });
  Object.defineProperty(window, 'SpeechSynthesisUtterance', {
    configurable: true,
    value: class {
      text: string;
      rate = 1;
      pitch = 1;
      volume = 1;
      lang = '';
      voice: FakeVoice | null = null;
      onerror: (() => void) | null = null;

      constructor(text: string) {
        this.text = text;
      }
    },
  });
  return { spoken, cancel, speakSpy };
}

function removeSpeech() {
  const win = window as unknown as {
    speechSynthesis?: unknown;
    SpeechSynthesisUtterance?: unknown;
  };
  delete win.speechSynthesis;
  delete win.SpeechSynthesisUtterance;
}

afterEach(() => {
  removeSpeech();
  vi.restoreAllMocks();
});

describe('voiceAvailable', () => {
  it('is false when the browser has no speech engine', () => {
    expect(voiceAvailable()).toBe(false);
  });

  it('is true once speechSynthesis and the utterance constructor both exist', () => {
    installSpeech();
    expect(voiceAvailable()).toBe(true);
  });
});

describe('speak without an engine', () => {
  it('is an inert no-op rather than a throw', () => {
    expect(() => speak('Move 1: White plays pawn to e4.')).not.toThrow();
    expect(() => stopSpeaking()).not.toThrow();
  });
});

describe('speak', () => {
  it('cancels whatever was saying before starting', () => {
    // Fast stepping must replace the commentary, not queue a backlog of it.
    const { cancel: cancelSpy } = installSpeech();
    speak('first');
    speak('second');
    expect(cancelSpy).toHaveBeenCalledTimes(2);
  });

  it('says nothing for blank text', () => {
    const { spoken: said } = installSpeech();
    speak('   ');
    expect(said).toEqual([]);
  });

  it('reads calm: slower than default and a shade below the default pitch', () => {
    const { speakSpy } = installSpeech();
    speak('Knight to f3.');
    const utterance = speakSpy.mock.calls[0][0] as { rate: number; pitch: number; volume: number };
    expect(utterance.rate).toBeLessThan(1);
    expect(utterance.pitch).toBeLessThan(1);
    expect(utterance.volume).toBe(1);
  });

  it('prefers the first hinted voice that is actually installed', () => {
    const { speakSpy } = installSpeech([
      { name: 'Samantha', lang: 'en-US' },
      { name: 'Daniel', lang: 'en-GB' },
      { name: 'Google UK English Male', lang: 'en-GB' },
    ]);
    speak('Knight to f3.');
    const utterance = speakSpy.mock.calls[0][0] as { voice: { name: string }; lang: string };
    expect(utterance.voice.name).toBe('Daniel');
    expect(utterance.lang).toBe('en-GB');
  });

  it('falls back through british, any english, then the platform default', () => {
    const cases: [FakeVoice[], string][] = [
      [
        [
          { name: 'Zarina', lang: 'es-ES' },
          { name: 'Oliver', lang: 'en-GB' },
        ],
        'Oliver',
      ],
      [
        [
          { name: 'Zarina', lang: 'es-ES' },
          { name: 'Karen', lang: 'en-AU' },
        ],
        'Karen',
      ],
      [[{ name: 'Zarina', lang: 'es-ES', default: true }], 'Zarina'],
    ];
    for (const [voices, expected] of cases) {
      const { speakSpy } = installSpeech(voices);
      speak('Test.');
      expect((speakSpy.mock.calls[0][0] as { voice: { name: string } }).voice.name).toBe(expected);
      removeSpeech();
    }
  });

  it('still speaks with the platform voice when the list is not loaded yet', () => {
    // Chrome returns an empty list until its voices arrive; narration must not
    // be contingent on that race.
    const { spoken: said, speakSpy } = installSpeech([]);
    speak('Test.');
    expect(said).toEqual(['Test.']);
    expect(speakSpy.mock.calls[0][0]).toMatchObject({ voice: null });
  });

  it('swallows an engine error instead of breaking the review page', () => {
    installSpeech();
    const engine = window.speechSynthesis as unknown as {
      speak: (u: { onerror: (() => void) | null }) => void;
    };
    vi.spyOn(engine, 'speak').mockImplementation((utterance) => {
      utterance.onerror?.();
    });
    expect(() => speak('Move 4: bishop takes f7, checkmate.')).not.toThrow();
  });

  it('stops the narrator when the page unmounts', () => {
    const { cancel: cancelSpy } = installSpeech();
    speak('Knight to f3.');
    stopSpeaking();
    expect(cancelSpy).toHaveBeenCalledTimes(2);
  });
});

describe('chunkText', () => {
  const long = [
    'Move 12: White plays bishop to b5, exactly what the engine wanted.',
    'This is the Ruy Lopez: Morphy Defense, the main line of an old opening.',
    "White's win expectancy here is 56 percent, and the position stays balanced.",
    'Keep the bishop pair and the f6 knight under observation and the pawn stays safe.',
  ].join(' ');

  it('keeps short narration in one piece', () => {
    expect(chunkText('Knight to f3. Solid.')).toEqual(['Knight to f3. Solid.']);
  });

  it('splits long narration and loses nothing', () => {
    const chunks = chunkText(long);
    expect(chunks.length).toBeGreaterThan(1);
    expect(chunks.join(' ')).toBe(long);
    for (const chunk of chunks) expect(chunk.length).toBeLessThanOrEqual(180);
  });

  it('breaks between sentences, never inside one that fits', () => {
    const one = 'Move 12: White plays bishop to b5, exactly what the engine wanted.';
    const two = "White's win expectancy here is 56 percent, and the position stays balanced.";
    expect(chunkText(`${one} ${two} ${one}`, 100)).toEqual([one, two, one]);
  });

  it('never tears a decimal like "1.5 pawns" in half', () => {
    const text = 'White is better here by 1.5 pawns, which the engine can prove.';
    const chunks = chunkText(text, 24);
    expect(chunks.join(' ')).toBe(text);
    for (const chunk of chunks) expect(chunk).not.toMatch(/(^|\s)\d+\.$/);
    expect(chunks.some((chunk) => chunk.includes('1.5'))).toBe(true);
  });

  it('leaves a single oversized word intact', () => {
    const word = 'Supercalifragilisticexpialidocious'.repeat(6);
    expect(chunkText(word, 20)).toEqual([word]);
  });
});
