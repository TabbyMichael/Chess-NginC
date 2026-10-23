/**
 * Application shell and routes (WEB-004).
 * Public: /login, /register, /forgot-password, /reset-password.
 * Protected: dashboard + game pages.
 * Header: brand + nav left, theme switcher and account menu right;
 * logout lives in the account menu, not in page content.
 */
import { Link, NavLink, Route, Routes } from 'react-router-dom';

import RequireAuth from './app/RequireAuth';
import { useAuth } from './app/useAuth';
import ThemeToggle from './components/ThemeToggle';
import UserMenu from './components/UserMenu';
import Dashboard from './pages/Dashboard';
import GamePage from './pages/GamePage';
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage } from './pages/AuthPages';

function Header() {
  const { user } = useAuth();
  return (
    <header className="app-header">
      <div className="header-inner">
        <Link to="/" className="brand" aria-label="Chess NginC home">
          <span className="brand-mark" aria-hidden="true">
            ♞
          </span>
          <span>
            <span className="brand-name">Chess NginC</span>
            <span className="brand-tag">Play · Improve · Compete</span>
          </span>
        </Link>
        {user && (
          <nav className="header-nav" aria-label="primary">
            <NavLink
              to="/"
              end
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              Home
            </NavLink>
          </nav>
        )}
        <div className="header-actions">
          <ThemeToggle />
          {user ? (
            <UserMenu />
          ) : (
            <>
              <Link to="/login" className="btn btn-ghost btn-small">
                Log in
              </Link>
              <Link to="/register" className="btn btn-primary btn-small">
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <Header />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/games/:id"
          element={
            <RequireAuth>
              <GamePage />
            </RequireAuth>
          }
        />
        <Route
          path="*"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
      </Routes>
      <footer className="app-footer">Chess NginC — play the position, not the clock.</footer>
    </div>
  );
}
