// Google OAuth (implicit flow) and token storage for the web client.
//
// Web-only: there is no Chrome extension API surface to detect or remove
// here. The retired extension implementation is preserved by Git tag.

// Public web OAuth client id (not secret - sent to the browser regardless);
// see backend/config.py's `google_web_client_id`, the same value.
const GOOGLE_WEB_CLIENT_ID =
  "258289407737-mdh4gleu91oug8f5g8jqkt75f62te9kv.apps.googleusercontent.com";
const GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth";

const TOKEN_STORAGE_KEY = "ai_recruiting_agent_auth";
export const OAUTH_STATE_KEY = "ai_recruiting_agent_oauth_state";
export const OAUTH_NONCE_KEY = "ai_recruiting_agent_oauth_nonce";

function randomToken(byteLength = 24) {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

/** @returns {Promise<{accessToken: string, idToken: string, expiresAt: number} | null>} */
export async function getAuthToken() {
  let stored;
  try {
    stored = localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
  if (!stored) return null;
  try {
    const token = JSON.parse(stored);
    if (token && token.expiresAt > Date.now()) return token;
  } catch {
    // fall through to null below
  }
  return null;
}

export async function saveAuthToken(token) {
  try {
    localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(token));
  } catch {
    // ignore storage failures (private browsing, quota, etc.)
  }
}

export async function clearAuthToken() {
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // ignore
  }
}

export async function checkUserAuthentication() {
  return (await getAuthToken()) !== null;
}

/** Redirects the browser to Google's consent screen; does not return. */
export function login() {
  const state = randomToken();
  const nonce = randomToken();
  try {
    sessionStorage.setItem(OAUTH_STATE_KEY, state);
    sessionStorage.setItem(OAUTH_NONCE_KEY, nonce);
  } catch {
    // if storage is unavailable, auth-callback.html simply skips verification
  }

  const redirectUri = `${window.location.origin}/app/auth-callback.html`;
  const params = new URLSearchParams({
    client_id: GOOGLE_WEB_CLIENT_ID,
    redirect_uri: redirectUri,
    response_type: "token id_token",
    scope: "openid email profile",
    prompt: "consent",
    state,
    nonce,
  });
  window.location.href = `${GOOGLE_AUTH_URL}?${params.toString()}`;
}

export async function logout() {
  await clearAuthToken();
}

/** @returns {string | null} the email claim from the stored ID token, if any. */
export async function getUserEmail() {
  const token = await getAuthToken();
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.idToken.split(".")[1]));
    return payload.email || null;
  } catch {
    return null;
  }
}
