/**
 * Celebration toast tests (ACH-007): one achievement at a time, a rarity
 * kicker, manual close, and an auto-dismiss timer that re-arms when the next
 * unlock arrives.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import AchievementCelebration, { CELEBRATION_MS } from './AchievementCelebration';
import type { AchievementResponse } from '../lib/api-types';

function item(key: string, overrides: Partial<AchievementResponse> = {}): AchievementResponse {
  return {
    key,
    title: `Title ${key}`,
    description: `Description ${key}`,
    metric: 'moves_total',
    threshold: 10,
    tier: 'gold',
    group: 'play',
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('AchievementCelebration', () => {
  it('renders nothing with an empty queue', () => {
    const { container } = render(<AchievementCelebration items={[]} onDismiss={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the first queued achievement with its rarity', () => {
    render(
      <AchievementCelebration
        items={[item('a'), item('b', { tier: 'bronze' })]}
        onDismiss={() => {}}
      />,
    );
    expect(screen.getByRole('status')).toHaveTextContent('Title a');
    expect(screen.getByText('Achievement unlocked · Gold')).toBeInTheDocument();
    expect(screen.queryByText('Title b')).not.toBeInTheDocument();
  });

  it('closes on request', () => {
    const onDismiss = vi.fn();
    render(<AchievementCelebration items={[item('a')]} onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss Title a' }));
    expect(onDismiss).toHaveBeenCalledWith('a');
  });

  it('auto-dismisses after the celebration window', () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    render(<AchievementCelebration items={[item('a')]} onDismiss={onDismiss} />);

    vi.advanceTimersByTime(CELEBRATION_MS - 500);
    expect(onDismiss).not.toHaveBeenCalled();
    vi.advanceTimersByTime(500);
    expect(onDismiss).toHaveBeenCalledWith('a');
  });

  it('restarts the window when a different achievement is shown', () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    const view = render(<AchievementCelebration items={[item('a')]} onDismiss={onDismiss} />);

    vi.advanceTimersByTime(CELEBRATION_MS - 500);
    view.rerender(<AchievementCelebration items={[item('b')]} onDismiss={onDismiss} />);
    vi.advanceTimersByTime(500);
    expect(onDismiss).not.toHaveBeenCalled();

    vi.advanceTimersByTime(CELEBRATION_MS);
    expect(onDismiss).toHaveBeenCalledWith('b');
  });
});
