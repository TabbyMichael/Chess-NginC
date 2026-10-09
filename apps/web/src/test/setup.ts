import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';

// Vitest runs without `globals`, so RTL auto-cleanup never registers itself.
// Without this, rendered DOM leaks between tests and queries find duplicates.
afterEach(() => {
  cleanup();
});
