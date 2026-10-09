import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import App from './App';
import { AuthProvider } from './app/AuthContext';
import { ApiError, api } from './lib/api-client';

function renderApp(path = '/') {
  const user = userEvent.setup();
  const view = render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return { user, ...view };
}

describe('App routing (WEB-004/005/006/008)', () => {
  it('redirects unauthenticated users from / to the login page', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument();
  });

  it('shows a session-restoration loading state before /auth/me resolves', () => {
    vi.spyOn(api, 'me').mockReturnValueOnce(new Promise(() => undefined));
    renderApp('/');
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('renders the dashboard when a session is restored', async () => {
    vi.spyOn(api, 'me').mockResolvedValueOnce({ id: 1, email: 'a@b.co' });
    vi.spyOn(api, 'listGames').mockResolvedValueOnce([]);
    renderApp('/');
    expect(await screen.findByText('a@b.co')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'New game' })).toBeInTheDocument();
  });

  it('logs in from the login form and lands on the dashboard', async () => {
    const me = vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    const login = vi.spyOn(api, 'login').mockResolvedValueOnce({ id: 1, email: 'a@b.co' });
    const list = vi.spyOn(api, 'listGames').mockResolvedValueOnce([]);
    const { user } = renderApp('/login');

    await user.type(screen.getByLabelText('Email'), 'a@b.co');
    await user.type(screen.getByLabelText('Password'), 'supersecret1');
    await user.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByText('a@b.co')).toBeInTheDocument();
    expect(login).toHaveBeenCalledWith({ email: 'a@b.co', password: 'supersecret1' });
    expect(me).toHaveBeenCalled();
    expect(list).toHaveBeenCalled();
  });

  it('rejects a short password before calling the API (WEB-025)', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    const login = vi.spyOn(api, 'login');
    const { user } = renderApp('/login');

    await user.type(screen.getByLabelText('Email'), 'a@b.co');
    await user.type(screen.getByLabelText('Password'), 'short');
    await user.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('at least 8 characters');
    expect(login).not.toHaveBeenCalled();
  });

  it('surfaces server errors as an alert', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    vi.spyOn(api, 'login').mockRejectedValueOnce(new ApiError(401, 'Invalid email or password'));
    const { user } = renderApp('/login');

    await user.type(screen.getByLabelText('Email'), 'a@b.co');
    await user.type(screen.getByLabelText('Password'), 'supersecret1');
    await user.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password');
  });
});
