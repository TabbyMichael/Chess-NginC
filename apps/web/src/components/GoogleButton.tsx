/**
 * "Continue with Google" via Google Identity Services (GIS).
 * Google owns the button rendering (its terms require the real widget); we
 * hand it a container and send the returned ID token to the backend, which
 * verifies it against GOOGLE_CLIENT_ID. Renders nothing when
 * VITE_GOOGLE_CLIENT_ID is not configured — no broken buttons in the UI.
 */
import { useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../app/useAuth';
import { GOOGLE_CLIENT_ID } from '../lib/google-auth';

const CLIENT_ID = GOOGLE_CLIENT_ID;
const GSI_SRC = 'https://accounts.google.com/gsi/client';

interface CredentialResponse {
  credential?: string;
}
interface GoogleIdApi {
  initialize(config: { client_id: string; callback: (r: CredentialResponse) => void }): void;
  renderButton(
    el: HTMLElement,
    options: { theme?: string; size?: string; text?: string; width?: number },
  ): void;
}

declare global {
  interface Window {
    google?: { accounts?: { id?: GoogleIdApi } };
  }
}

// Load the GIS script at most once for the whole app.
let gsiLoad: Promise<void> | null = null;
function loadGsi(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!gsiLoad) {
    gsiLoad = new Promise<void>((resolve, reject) => {
      const script = document.createElement('script');
      script.src = GSI_SRC;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => {
        gsiLoad = null;
        reject(new Error('Failed to load Google sign-in'));
      };
      document.head.appendChild(script);
    });
  }
  return gsiLoad;
}

export default function GoogleButton() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!CLIENT_ID) return;
    let cancelled = false;
    loadGsi()
      .then(() => {
        const id = window.google?.accounts?.id;
        const el = containerRef.current;
        if (cancelled || !id || !el) return;
        const dark = document.documentElement.dataset.theme === 'dark';
        id.initialize({
          client_id: CLIENT_ID,
          callback: (resp) => {
            if (!resp.credential) return;
            loginWithGoogle(resp.credential)
              .then(() => {
                const from = (location.state as { from?: string } | null)?.from ?? '/';
                navigate(from, { replace: true });
              })
              .catch(() => {
                // Error surfaces via the auth context `error` on the page.
              });
          },
        });
        id.renderButton(el, {
          theme: dark ? 'filled_black' : 'outline',
          size: 'large',
          text: 'continue_with',
          width: 300,
        });
      })
      .catch(() => {
        // GIS unreachable (offline/blocked): leave the container empty.
      });
    return () => {
      cancelled = true;
    };
  }, [loginWithGoogle, navigate, location]);

  if (!CLIENT_ID) return null;
  return <div className="google-btn-wrap" ref={containerRef} />;
}
