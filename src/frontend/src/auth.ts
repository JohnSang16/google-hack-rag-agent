// Discord OAuth token handling. The backend redirects to /#token=<signed token>
// after login; we stash it in localStorage and send it as a bearer header.

const TOKEN_KEY = 'progsu_auth_token';

export interface Me {
  tier: string;
  username: string | null;
  can_plan: boolean;
  can_calendar: boolean;
  can_gmail_send: boolean;
  financial_access: boolean;
  auth_configured: boolean;
}

export function captureTokenFromHash(): void {
  const match = window.location.hash.match(/token=([^&]+)/);
  if (match) {
    localStorage.setItem(TOKEN_KEY, match[1]);
    history.replaceState(null, '', window.location.pathname + window.location.search);
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
