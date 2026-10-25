/** Registration, login, and password-reset flows (WEB-005/006/025). */
import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';

import { useAuth } from '../app/useAuth';
import GoogleButton from '../components/GoogleButton';
import { Button } from '../components/ui/Button';
import { ApiError, api } from '../lib/api-client';
import { googleEnabled } from '../lib/google-auth';

function useAuthForm(submit: (email: string, password: string) => Promise<void>) {
  const navigate = useNavigate();
  const location = useLocation();
  const { error, clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    clearError();
    setLocalError(null);
    if (password.length < 8) {
      setLocalError('Password must be at least 8 characters.');
      return;
    }
    setBusy(true);
    try {
      await submit(email.trim(), password);
      const from = (location.state as { from?: string } | null)?.from ?? '/';
      navigate(from, { replace: true });
    } catch {
      // Error surfaces via context; keep form state for retry.
    } finally {
      setBusy(false);
    }
  }
  return { email, setEmail, password, setPassword, busy, error: localError ?? error, onSubmit };
}

export function RegisterPage() {
  const { register } = useAuth();
  const form = useAuthForm(register);
  return (
    <main className="auth" id="main-content">
      <div className="auth-card">
        <h1>Create Account</h1>
        <p className="u-muted">Sign in to start playing.</p>
        <form onSubmit={form.onSubmit} aria-label="registration form">
          <div className="field">
            <label htmlFor="register-email">Email</label>
            <input
              id="register-email"
              className="input"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              required
              value={form.email}
              onChange={(e) => form.setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="register-password">Password (min 8 characters)</label>
            <input
              id="register-password"
              className="input"
              name="password"
              type="password"
              autoComplete="new-password"
              placeholder="At least 8 characters"
              required
              value={form.password}
              onChange={(e) => form.setPassword(e.target.value)}
            />
          </div>
          {form.error && (
            <p role="alert" className="error">
              {form.error}
            </p>
          )}
          <Button type="submit" variant="primary" disabled={form.busy} className="w-full">
            {form.busy ? 'Creating…' : 'Create account'}
          </Button>
        </form>
        {googleEnabled() && <div className="auth-divider">or</div>}
        <GoogleButton />
        <p className="auth-alt">
          Have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </main>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const form = useAuthForm(login);
  return (
    <main className="auth" id="main-content">
      <div className="auth-card">
        <h1>Log in</h1>
        <p className="u-muted">Welcome back to the board.</p>
        <form onSubmit={form.onSubmit} aria-label="login form">
          <div className="field">
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              className="input"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              required
              value={form.email}
              onChange={(e) => form.setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <div className="field-row">
              <label htmlFor="login-password">Password</label>
              <Link to="/forgot-password">Forgot password?</Link>
            </div>
            <input
              id="login-password"
              className="input"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={form.password}
              onChange={(e) => form.setPassword(e.target.value)}
            />
          </div>
          {form.error && (
            <p role="alert" className="error">
              {form.error}
            </p>
          )}
          <Button type="submit" variant="primary" disabled={form.busy} className="w-full">
            {form.busy ? 'Logging in…' : 'Log in'}
          </Button>
        </form>
        {googleEnabled() && <div className="auth-divider">or</div>}
        <GoogleButton />
        <p className="auth-alt">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </div>
    </main>
  );
}

export function ForgotPasswordPage() {
  const { clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    clearError();
    setError(null);
    setBusy(true);
    try {
      await api.forgotPassword({ email: email.trim() });
      // Always report success: the endpoint never reveals whether the
      // address is registered (SEC-016 anti-enumeration).
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth" id="main-content">
      <div className="auth-card">
        <h1>Forgot password</h1>
        {sent ? (
          <div className="auth-success" role="status">
            <h2>Check your inbox</h2>
            <p>
              If an account exists for <strong>{email.trim()}</strong>, a reset link is on its way.
              The link expires after an hour.
            </p>
          </div>
        ) : (
          <>
            <p className="u-muted">Enter your email and we’ll send you a reset link.</p>
            <form onSubmit={onSubmit} aria-label="forgot password form">
              <div className="field">
                <label htmlFor="forgot-email">Email</label>
                <input
                  id="forgot-email"
                  className="input"
                  name="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              {error && (
                <p role="alert" className="error">
                  {error}
                </p>
              )}
              <Button type="submit" variant="primary" disabled={busy} className="w-full">
                {busy ? 'Sending…' : 'Send reset link'}
              </Button>
            </form>
          </>
        )}
        <p className="auth-alt">
          Remembered it? <Link to="/login">Back to log in</Link>
        </p>
      </div>
    </main>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('The passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      await api.resetPassword({ token, password });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reset the password.');
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <main className="auth" id="main-content">
        <div className="auth-card">
          <h1>Reset password</h1>
          <div className="error" role="alert">
            This reset link is not valid. Request a new one and try again.
          </div>
          <p className="auth-alt">
            <Link to="/forgot-password">Request a new link</Link>
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="auth" id="main-content">
      <div className="auth-card">
        <h1>Choose a new password</h1>
        {done ? (
          <div className="auth-success" role="status">
            <h2>Password updated</h2>
            <p>Your existing sessions were signed out. Log in with your new password.</p>
          </div>
        ) : (
          <>
            <p className="u-muted">Pick a strong password of at least 8 characters.</p>
            <form onSubmit={onSubmit} aria-label="reset password form">
              <div className="field">
                <label htmlFor="reset-password">New password</label>
                <input
                  id="reset-password"
                  className="input"
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="reset-confirm">Confirm password</label>
                <input
                  id="reset-confirm"
                  className="input"
                  name="confirm"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                />
              </div>
              {error && (
                <p role="alert" className="error">
                  {error}
                </p>
              )}
              <Button type="submit" variant="primary" disabled={busy} className="w-full">
                {busy ? 'Saving…' : 'Set new password'}
              </Button>
            </form>
          </>
        )}
        <p className="auth-alt">
          <Link to="/login">Back to log in</Link>
        </p>
      </div>
    </main>
  );
}
