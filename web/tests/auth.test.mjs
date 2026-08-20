// Pure-logic tests for web/js/auth.js token storage. Run via
// `node --test web/tests/*.test.mjs` - no package.json, install step, or
// build tool (see docs/frontend.md's build/release contract).
import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

class MemoryStorage {
  #values = new Map();
  getItem(key) {
    return this.#values.has(key) ? this.#values.get(key) : null;
  }
  setItem(key, value) {
    this.#values.set(key, String(value));
  }
  removeItem(key) {
    this.#values.delete(key);
  }
  clear() {
    this.#values.clear();
  }
}

const originalLocalStorage = globalThis.localStorage;
const originalSessionStorage = globalThis.sessionStorage;

beforeEach(() => {
  globalThis.localStorage = new MemoryStorage();
  globalThis.sessionStorage = new MemoryStorage();
});

afterEach(() => {
  globalThis.localStorage = originalLocalStorage;
  globalThis.sessionStorage = originalSessionStorage;
});

const { getAuthToken, saveAuthToken, clearAuthToken, checkUserAuthentication } = await import("../js/auth.js");

test("stores and retrieves an unexpired auth token", async () => {
  const token = { accessToken: "access-token", idToken: "id-token", expiresAt: Date.now() + 60_000 };

  await saveAuthToken(token);

  assert.deepEqual(await getAuthToken(), token);
});

test("does not return an expired auth token", async () => {
  await saveAuthToken({ accessToken: "a", idToken: "i", expiresAt: Date.now() - 1 });

  assert.equal(await getAuthToken(), null);
});

test("clearAuthToken removes the stored token", async () => {
  await saveAuthToken({ accessToken: "a", idToken: "i", expiresAt: Date.now() + 60_000 });

  await clearAuthToken();

  assert.equal(await getAuthToken(), null);
});

test("checkUserAuthentication reflects stored-token presence", async () => {
  assert.equal(await checkUserAuthentication(), false);

  await saveAuthToken({ accessToken: "a", idToken: "i", expiresAt: Date.now() + 60_000 });

  assert.equal(await checkUserAuthentication(), true);
});
