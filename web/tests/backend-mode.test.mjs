import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

class MemoryStorage {
  #values = new Map();
  getItem(key) { return this.#values.get(key) ?? null; }
  setItem(key, value) { this.#values.set(key, String(value)); }
}

class FakeButton {
  classList = {
    hidden: true,
    toggle: (_name, force) => { this.classList.hidden = force; },
  };
  attributes = {};
  textContent = "";
  onclick = null;
  setAttribute(name, value) { this.attributes[name] = value; }
}

const originalDocument = globalThis.document;
const originalFetch = globalThis.fetch;
const originalLocation = globalThis.location;
const originalLocalStorage = globalThis.localStorage;
const backendMode = await import("../js/backend-mode.js");

let button;
let reloadCount;

beforeEach(() => {
  button = new FakeButton();
  globalThis.document = { getElementById: () => button };
  reloadCount = 0;
  globalThis.location = { reload: () => { reloadCount += 1; } };
  globalThis.localStorage = new MemoryStorage();
  backendMode._resetForTests();
});

afterEach(() => {
  globalThis.document = originalDocument;
  globalThis.fetch = originalFetch;
  globalThis.location = originalLocation;
  globalThis.localStorage = originalLocalStorage;
});

test("production hides the toggle and ignores a stale local selection", async () => {
  localStorage.setItem("ai_recruiting_agent_backend_mode", "local");
  globalThis.fetch = async () => new Response(JSON.stringify({ allow_local_api: false }));

  await backendMode.initBackendModeControl();

  assert.equal(button.classList.hidden, true);
  assert.equal(backendMode.getBackendMode(), "same-origin");
  assert.equal(backendMode.apiUrl("/api/v1/reviews"), "/api/v1/reviews");
});

test("development exposes a persistent local API toggle", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ allow_local_api: true }));

  await backendMode.initBackendModeControl();
  assert.equal(button.classList.hidden, false);
  assert.equal(button.textContent, "API: Same origin");

  button.onclick();
  assert.equal(button.textContent, "API: Local");
  assert.equal(button.attributes["aria-pressed"], "true");
  assert.equal(backendMode.apiUrl("/review"), "http://127.0.0.1:8000/review");
  assert.equal(localStorage.getItem("ai_recruiting_agent_backend_mode"), "local");
  assert.equal(reloadCount, 1);
});

test("a failed config request fails closed to same-origin", async () => {
  globalThis.fetch = async () => { throw new Error("offline"); };

  await backendMode.initBackendModeControl();

  assert.equal(button.classList.hidden, true);
  assert.equal(backendMode.apiUrl("/questions"), "/questions");
});
