/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Vitest does not restore spies by default; without this, mockResolvedValue
    // implementations leak between tests and real fetch calls get made.
    restoreMocks: true,
  },
});
