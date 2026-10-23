/**
 * Google Identity Services configuration. Kept out of the component file so
 * auth pages can gate their "or" divider without importing the widget.
 */
export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

export function googleEnabled(): boolean {
  return Boolean(GOOGLE_CLIENT_ID);
}
