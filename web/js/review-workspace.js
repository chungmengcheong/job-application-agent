// The orchestrator: wires workflow.js to the DOM, owns the job-description
// textarea and optional source-URL input, calls api.js/demo-api.js on
// submit/answer actions, and delegates rendering to review-display.js and
// redline.js. Supersedes extension-panel.tsx.
import * as api from "./api.js";
import * as auth from "./auth.js";
import * as demoApi from "./demo-api.js";
import { cleanText, parseSegments, renderRedline } from "./redline.js";
import { collectAnswers, renderFit, renderGapMap, renderQuestionsForm } from "./review-display.js";
import * as workflow from "./workflow.js";

// Local editing/session state - not durable server state and not the
// review/authenticated/demoMode/loading/error workflow state in workflow.js.
let liveResume = null;
let redlineSegments = null;
let editingIndex = null;

const el = (id) => document.getElementById(id);

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function handleApiError(err) {
  if (err?.status === 401) {
    workflow.setState({
      authenticated: false,
      review: null,
      loading: false,
      error: err.message || "Please log in again.",
    });
    return;
  }
  if (err?.status === 403) {
    workflow.setState({
      notAuthorized: true,
      review: null,
      loading: false,
      error: err.message || "You are not authorized for this resource.",
    });
    return;
  }
  workflow.setState({ loading: false, error: err?.message || "Something went wrong. Please try again." });
}

async function prefillSubmissionForm() {
  const state = workflow.getState();
  const hint = el("submission-hint");
  const jdField = el("job-description");

  if (state.demoMode) {
    hint.textContent =
      "Submit the job description below to see a demo review and redlined resume. Paste your own job description to exit demo mode.";
    if (jdField && !jdField.value) {
      try {
        jdField.value = await demoApi.demoJobDescription();
      } catch {
        // best-effort prefill; the user can still paste their own
      }
    }
    return;
  }

  if (!state.authenticated) {
    hint.textContent = "Log in to submit your own resume, or stay in demo mode to try a sample review.";
    return;
  }

  hint.textContent = "Generating a review can take up to two minutes.";
  if (!liveResume) {
    try {
      liveResume = await api.loadLiveResume();
    } catch (err) {
      handleApiError(err);
    }
  }
}

async function handleDemoToggle() {
  const state = workflow.getState();
  workflow.setState({ demoMode: !state.demoMode, review: null, error: null });
  await prefillSubmissionForm();
}

async function handleSubmitReview() {
  const jobDescription = el("job-description").value.trim();
  if (!jobDescription) return;
  const sourceUrl = el("source-url").value.trim();
  const state = workflow.getState();

  workflow.setState({ loading: true, error: null });
  try {
    if (state.demoMode) {
      const result = await demoApi.demoReview(jobDescription);
      workflow.setState({ review: { status: "awaiting_answers", result }, loading: false });
      return;
    }
    if (!state.authenticated) {
      workflow.setState({ loading: false, error: "Please log in to submit a review." });
      return;
    }
    if (!liveResume) {
      liveResume = await api.loadLiveResume();
    }
    const review = await api.createReview({ resume: liveResume, jobDescription, sourceUrl });
    workflow.setState({ review, loading: false });
    if (review.id) {
      history.pushState(null, "", `/app/reviews/${review.id}`);
    }
  } catch (err) {
    handleApiError(err);
  }
}

async function handleSubmitAnswers() {
  const state = workflow.getState();
  const questions = state.review?.result?.Questions;
  if (!questions) return;
  const qaPairs = collectAnswers(el("questions-form"), questions);

  workflow.setState({ loading: true, error: null });
  try {
    if (state.demoMode) {
      const result = await demoApi.demoQuestions(qaPairs);
      workflow.setState({ review: { status: "completed", result }, loading: false });
      return;
    }
    const updated = await api.submitAnswers(state.review.id, qaPairs);
    workflow.setState({ review: updated, loading: false });
  } catch (err) {
    handleApiError(err);
  }
}

async function handleLogout() {
  await auth.logout();
  liveResume = null;
  workflow.setState({ authenticated: false, review: null, error: null });
  await prefillSubmissionForm();
}

async function refreshAuthControls(state) {
  const container = el("auth-controls");
  if (!container) return;
  if (state.authenticated) {
    const email = await auth.getUserEmail();
    container.innerHTML = `
      <span class="user-email">${escapeHtml(email || "Signed in")}</span>
      <button type="button" id="logout-button">Log out</button>
    `;
    el("logout-button").onclick = handleLogout;
  } else {
    container.innerHTML = `<button type="button" id="login-button">Log in</button>`;
    el("login-button").onclick = () => auth.login();
  }
}

function updateDemoToggle(state) {
  const button = el("demo-toggle");
  if (!button) return;
  button.textContent = state.demoMode ? "Demo: ON" : "Demo: OFF";
  button.classList.toggle("demo-on", state.demoMode);
}

function renderRedlineView() {
  const container = el("redline-container");
  if (!container || !redlineSegments) return;
  const showRedlines = el("redline-toggle")?.checked ?? true;
  renderRedline(container, redlineSegments, {
    showRedlines,
    editingIndex,
    onChange: (patch) => {
      editingIndex = patch.editingIndex ?? null;
      renderRedlineView();
    },
  });
}

function onWorkflowRender(state, activeSection) {
  updateDemoToggle(state);
  refreshAuthControls(state);

  if (activeSection === "questions" && state.review?.result) {
    el("questions-fit").innerHTML = renderFit(state.review.result.Fit);
    el("questions-gap-map").innerHTML = renderGapMap(state.review.result.Gap_Map);
    el("questions-form").innerHTML = renderQuestionsForm(state.review.result.Questions || []);
  }

  if (activeSection === "result" && state.review?.result) {
    el("result-fit").innerHTML = renderFit(state.review.result.Fit);
    el("result-gap-map").innerHTML = renderGapMap(state.review.result.Gap_Map);
    redlineSegments = parseSegments(state.review.result.Tailored_Resume || "");
    editingIndex = null;
    renderRedlineView();
    el("result-fit").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function wireStaticControls() {
  el("demo-toggle").onclick = handleDemoToggle;
  el("submit-review").onclick = handleSubmitReview;
  el("submit-answers").onclick = handleSubmitAnswers;
  el("redline-toggle").onchange = renderRedlineView;
  el("copy-resume").onclick = async () => {
    if (!redlineSegments) return;
    try {
      await navigator.clipboard.writeText(cleanText(redlineSegments));
      const button = el("copy-resume");
      const original = button.textContent;
      button.textContent = "Copied!";
      setTimeout(() => {
        button.textContent = original;
      }, 2000);
    } catch {
      // clipboard permission denied; nothing more useful to do here
    }
  };

  const jdField = el("job-description");
  jdField.addEventListener("input", () => {
    if (workflow.getState().demoMode) {
      workflow.setState({ demoMode: false });
    }
  });
}

export async function initReviewWorkspace() {
  workflow.subscribe(onWorkflowRender);
  wireStaticControls();

  const authenticated = await auth.checkUserAuthentication();
  workflow.setState({ authenticated, demoMode: !authenticated });
  await prefillSubmissionForm();
}
