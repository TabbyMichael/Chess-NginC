/**
 * Application shell and routes (WEB-004).
 * Public: /login, /register. Protected: dashboard + game pages.
 */
import { Route, Routes } from 'react-router-dom';

import RequireAuth from './app/RequireAuth';
import Dashboard from './pages/Dashboard';
import GamePage from './pages/GamePage';
import { LoginPage, RegisterPage } from './pages/AuthPages';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
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
  );
}
