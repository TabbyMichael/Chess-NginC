/**
 * With a client ID configured, the GIS container mounts and the Google embed
 * script is requested. The unconfigured case (renders nothing) is covered by
 * the routing tests in App.test.tsx, where VITE_GOOGLE_CLIENT_ID is absent.
 */
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

async function mountConfiguredButton() {
  vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'test-client-id');
  // Re-import so the module-level CLIENT_ID constant sees the stubbed env.
  vi.resetModules();
  const [{ default: GoogleButton }, { AuthProvider }] = await Promise.all([
    import('./GoogleButton'),
    import('../app/AuthContext'),
  ]);
  const { container } = render(
    <MemoryRouter>
      <AuthProvider>
        <GoogleButton />
      </AuthProvider>
    </MemoryRouter>,
  );
  return container;
}

describe('GoogleButton (client ID configured)', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
    document
      .querySelectorAll('script[src*="accounts.google.com/gsi/client"]')
      .forEach((node) => node.remove());
  });

  it('mounts the GIS container', async () => {
    const container = await mountConfiguredButton();
    expect(container.querySelector('.google-btn-wrap')).not.toBeNull();
  });

  it('requests the Google Identity Services script', async () => {
    await mountConfiguredButton();
    expect(document.querySelector('script[src*="accounts.google.com/gsi/client"]')).not.toBeNull();
  });

  it('reports itself enabled so pages can show the "or" divider', async () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'test-client-id');
    vi.resetModules();
    const mod = await import('../lib/google-auth');
    expect(mod.googleEnabled()).toBe(true);
  });
});
