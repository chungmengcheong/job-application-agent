// Development-only API target override. Production defaults permanently to
// same-origin; the local option is enabled only after /app-config explicitly
// allows it, so stale or manually-added localStorage cannot bypass the server
// environment boundary.
const BACKEND_MODE_KEY = "ai_recruiting_agent_backend_mode";
const LOCAL_API_ORIGIN = "http://127.0.0.1:8000";

let localApiAllowed = false;
let mode = "same-origin";

function storedMode() {
  try {
    return localStorage.getItem(BACKEND_MODE_KEY);
  } catch {
    return null;
  }
}

function persistMode(value) {
  try {
    localStorage.setItem(BACKEND_MODE_KEY, value);
  } catch {
    // Storage is a convenience only; the in-memory selection still works.
  }
}

function render(button) {
  if (!button) return;
  button.classList.toggle("hidden", !localApiAllowed);
  button.textContent = mode === "local" ? "API: Local" : "API: Same origin";
  button.setAttribute("aria-pressed", String(mode === "local"));
}

export function apiUrl(path) {
  return localApiAllowed && mode === "local" ? `${LOCAL_API_ORIGIN}${path}` : path;
}

export function getBackendMode() {
  return mode;
}

export function setBackendMode(nextMode) {
  mode = localApiAllowed && nextMode === "local" ? "local" : "same-origin";
  persistMode(mode);
  return mode;
}

export async function initBackendModeControl() {
  const button = document.getElementById("api-mode-toggle");
  try {
    const response = await fetch("/app-config");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const config = await response.json();
    localApiAllowed = config?.allow_local_api === true;
  } catch {
    localApiAllowed = false;
  }

  setBackendMode(localApiAllowed ? storedMode() : "same-origin");
  render(button);
  if (localApiAllowed && button) {
    button.onclick = () => {
      setBackendMode(mode === "local" ? "same-origin" : "local");
      render(button);
      // Do not carry a cached resume or review across backend boundaries.
      globalThis.location?.reload?.();
    };
  }
}

export function _resetForTests() {
  localApiAllowed = false;
  mode = "same-origin";
}
