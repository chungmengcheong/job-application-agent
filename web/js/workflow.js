// Durable / workflow / local state boundary (see docs/frontend.md).
//
// `review` is either the server's own `ReviewOut` (live mode) or a locally
// synthesized equivalent shape (demo mode - see demo-api.js callers in
// review-workspace.js); either way it is the one source of truth for what
// stage the review is in. There is no separate client-side workflow-state
// enum kept in sync by hand: display derives from `review?.status`
// (`processing | awaiting_answers | completed | failed`, the same enum
// `backend/review_store.py` uses) plus a handful of independent flags below.
// Local editing state (unsent answers, redline accept/reject/edit overrides,
// copy feedback) is not part of this module - see review-workspace.js and
// redline.js.

const SECTION_IDS = ["loading", "review"];
const TAB_IDS = ["job-description", "job-fit", "resume"];

const state = {
  review: null,
  authenticated: false,
  demoMode: true,
  loading: false,
  activeTab: "job-description",
  error: null,
  // Distinct from `authenticated`: a 403 means the session is still valid
  // but this resource is forbidden. A 401 instead clears `authenticated`.
  notAuthorized: false,
};

let onRender = () => {};

export function getState() {
  return state;
}

/** Registers the one callback that fills in section content after each render(). */
export function subscribe(renderFn) {
  onRender = renderFn;
}

export function setState(patch) {
  Object.assign(state, patch);
  render();
}

export function setActiveTab(tabId) {
  if (!TAB_IDS.includes(tabId)) return;
  state.activeTab = tabId;
  render();
}

function sectionFor(s) {
  if (s.loading) return "loading";
  return "review";
}

function render() {
  const active = sectionFor(state);
  for (const id of SECTION_IDS) {
    document.getElementById(`section-${id}`)?.classList.toggle("hidden", id !== active);
  }
  const errorBanner = document.getElementById("error-banner");
  if (errorBanner) {
    errorBanner.classList.toggle("hidden", !state.error);
    errorBanner.textContent = state.error || "";
  }
  onRender(state, active);
}
