export const AUTH_TOKEN_KEY = "life-os.access-token";
export const REFRESH_TOKEN_KEY = "life-os.refresh-token";
export const EXPIRES_AT_KEY = "life-os.expires-at";
export const DEVELOPMENT_TOKEN = "dev-local-token";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export function hasSupabaseConfig() {
  return Boolean(supabaseUrl && supabaseAnonKey);
}

export function getAuthToken() {
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

function setSession(accessToken: string, refreshToken?: string | null, expiresIn?: number | null) {
  window.localStorage.setItem(AUTH_TOKEN_KEY, accessToken);
  if (refreshToken) {
    window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }
  if (expiresIn) {
    window.localStorage.setItem(EXPIRES_AT_KEY, `${Date.now() + expiresIn * 1000}`);
  }
  window.dispatchEvent(new Event("life-os:auth-changed"));
}

export function setDevelopmentToken() {
  setSession(DEVELOPMENT_TOKEN);
}

export function clearAuthToken() {
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  window.localStorage.removeItem(EXPIRES_AT_KEY);
  window.dispatchEvent(new Event("life-os:auth-changed"));
}

async function supabaseTokenRequest(grantType: "password" | "refresh_token", body: Record<string, string>) {
  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error("Supabase is not configured.");
  }
  const response = await fetch(`${supabaseUrl.replace(/\/$/, "")}/auth/v1/token?grant_type=${grantType}`, {
    method: "POST",
    headers: {
      apikey: supabaseAnonKey,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    throw new Error("Authentication failed.");
  }
  return response.json() as Promise<{ access_token: string; refresh_token?: string; expires_in?: number }>;
}

export async function signInWithPassword(email: string, password: string) {
  if (!hasSupabaseConfig()) {
    setDevelopmentToken();
    return;
  }
  const session = await supabaseTokenRequest("password", { email, password });
  setSession(session.access_token, session.refresh_token, session.expires_in);
}

export async function refreshSession() {
  const refreshToken = window.localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshToken || !hasSupabaseConfig()) {
    return false;
  }
  const session = await supabaseTokenRequest("refresh_token", { refresh_token: refreshToken });
  setSession(session.access_token, session.refresh_token ?? refreshToken, session.expires_in);
  return true;
}

export async function restoreSession() {
  const token = getAuthToken();
  if (!token) {
    return false;
  }
  if (token === DEVELOPMENT_TOKEN) {
    return true;
  }
  const expiresAt = Number(window.localStorage.getItem(EXPIRES_AT_KEY) ?? "0");
  if (expiresAt && expiresAt - Date.now() < 60_000) {
    return refreshSession();
  }
  return true;
}

export async function getValidAuthToken() {
  const ok = await restoreSession();
  return ok ? getAuthToken() : null;
}

export async function signOut() {
  if (hasSupabaseConfig()) {
    const token = getAuthToken();
    if (token && supabaseUrl && supabaseAnonKey) {
      await fetch(`${supabaseUrl.replace(/\/$/, "")}/auth/v1/logout`, {
        method: "POST",
        headers: { apikey: supabaseAnonKey, Authorization: `Bearer ${token}` }
      }).catch(() => undefined);
    }
  }
  clearAuthToken();
}
