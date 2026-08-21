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
let baselineResume = null;
let currentJobDescription = "";
let reviewQuestions = [];
let questionAnswers = [];
let redlineSegments = null;
let editingIndex = null;
let renderedReview = null;

const el = (id) => document.getElementById(id);

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function getQuestionsForReview(review) {
  if (Array.isArray(review?.questions)) return review.questions;
  if (Array.isArray(review?.result?.Questions)) return review.result.Questions;
  if (Array.isArray(review?.answers)) return review.answers.map((pair) => pair.question);
  return [];
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
    if (!baselineResume) {
      try {
        baselineResume = await demoApi.demoResume();
      } catch {
        // best-effort load; the tab will explain that the resume is unavailable
      }
    }
    workflow.setState({});
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
      baselineResume = liveResume;
    } catch (err) {
      handleApiError(err);
    }
  }
  workflow.setState({});
}

async function handleDemoToggle() {
  const state = workflow.getState();
  baselineResume = null;
  currentJobDescription = "";
  reviewQuestions = [];
  questionAnswers = [];
  renderedReview = null;
  workflow.setState({ demoMode: !state.demoMode, review: null, error: null, activeTab: "job-description" });
  await prefillSubmissionForm();
}

async function handleSubmitReview() {
  const jobDescription = el("job-description").value.trim();
  if (!jobDescription) return;
  const sourceUrl = el("source-url").value.trim();
  const state = workflow.getState();

  currentJobDescription = jobDescription;
  workflow.setState({ loading: true, error: null });
  try {
    if (state.demoMode) {
      const [result, resume] = await Promise.all([
        demoApi.demoReview(jobDescription),
        demoApi.demoResume(),
      ]);
      baselineResume = resume;
      workflow.setState({
        review: {
          status: "awaiting_answers",
          job_description: jobDescription,
          resume,
          questions: result.Questions || [],
          answers: demoApi.demoAnswers(result.Questions || []),
          result,
        },
        loading: false,
        activeTab: "job-fit",
      });
      return;
    }
    if (!state.authenticated) {
      workflow.setState({ loading: false, error: "Please log in to submit a review." });
      return;
    }
    if (!liveResume) {
      liveResume = await api.loadLiveResume();
    }
    baselineResume = liveResume;
    const review = await api.createReview({ resume: liveResume, jobDescription, sourceUrl });
    workflow.setState({
      review: {
        ...review,
        job_description: review.job_description || jobDescription,
        resume: review.resume || liveResume,
        questions: review.questions || getQuestionsForReview(review),
        answers: review.answers || [],
      },
      loading: false,
      activeTab: "job-fit",
    });
    if (review.id) {
      history.pushState(null, "", `/app/reviews/${review.id}`);
    }
  } catch (err) {
    handleApiError(err);
  }
}

async function handleSubmitAnswers() {
  const state = workflow.getState();
  const questions = reviewQuestions.length ? reviewQuestions : getQuestionsForReview(state.review);
  if (!questions.length) return;
  const qaPairs = collectAnswers(el("questions-form"), questions);
  questionAnswers = qaPairs;

  workflow.setState({ loading: true, error: null });
  try {
    if (state.demoMode) {
      const result = await demoApi.demoQuestions(qaPairs);
      workflow.setState({
        review: { ...state.review, status: "completed", questions, answers: qaPairs, result },
        loading: false,
        activeTab: "job-fit",
      });
      return;
    }
    const updated = await api.submitAnswers(state.review.id, qaPairs);
    workflow.setState({
      review: {
        ...updated,
        job_description: updated.job_description || state.review.job_description || currentJobDescription,
        resume: updated.resume || state.review.resume || baselineResume,
        questions: updated.questions || questions,
        answers: updated.answers || qaPairs,
      },
      loading: false,
      activeTab: "job-fit",
    });
  } catch (err) {
    handleApiError(err);
  }
}

async function handleLogout() {
  await auth.logout();
  liveResume = null;
  baselineResume = null;
  currentJobDescription = "";
  reviewQuestions = [];
  questionAnswers = [];
  renderedReview = null;
  workflow.setState({ authenticated: false, review: null, error: null, activeTab: "job-description" });
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

function renderReviewTabs(state) {
  const hasReview = Boolean(state.review);
  const isCompleted = state.review?.status === "completed";
  const labels = {
    "job-description": "Job Description",
    "job-fit": isCompleted ? "Revised Job Fit" : "Job fit",
    questions: "Questions for You",
    resume: isCompleted ? "Proposed resume" : "Resume",
  };
  const activeTab = hasReview
    ? (labels[state.activeTab] ? state.activeTab : "job-fit")
    : (state.activeTab === "resume" ? "resume" : "job-description");

  for (const [tabId, label] of Object.entries(labels)) {
    const tab = el(`tab-${tabId}`);
    const panel = el(`tab-panel-${tabId}`);
    const isActive = tabId === activeTab;
    if (tab) {
      tab.textContent = label;
      tab.setAttribute("aria-selected", String(isActive));
      tab.tabIndex = isActive ? 0 : -1;
      tab.disabled = !hasReview && ["job-fit", "questions"].includes(tabId);
      tab.setAttribute("aria-disabled", String(tab.disabled));
    }
    if (panel) {
      panel.classList.toggle("hidden", !isActive);
      panel.setAttribute("aria-hidden", String(!isActive));
    }
  }

  el("submission-content")?.classList.toggle("hidden", hasReview);
  el("review-job-description-view")?.classList.toggle("hidden", !hasReview);
  el("submit-answers")?.classList.toggle("hidden", !hasReview || reviewQuestions.length === 0);
  el("job-fit-actions")?.classList.toggle("hidden", !hasReview);
  const updateAnswersButton = el("update-answers");
  if (updateAnswersButton) {
    updateAnswersButton.textContent = isCompleted
      ? "Update answers to questions"
      : "Provide answers to questions";
  }
  const proposedResumeButton = el("see-proposed-resume");
  if (proposedResumeButton) proposedResumeButton.disabled = !isCompleted;
  el("baseline-resume-view")?.classList.toggle("hidden", isCompleted);
  el("revised-resume-view")?.classList.toggle("hidden", !isCompleted);
}

function renderInitialState(state) {
  const resume = el("baseline-resume");
  if (!resume) return;
  resume.textContent = baselineResume
    || (state.demoMode || state.authenticated
      ? "Loading your resume…"
      : "Your resume will appear here after you log in or turn on demo mode.");
  reviewQuestions = [];
  questionAnswers = [];
  el("questions-form").innerHTML = "";
  el("submit-answers")?.classList.add("hidden");
}

function renderReviewContent(review) {
  currentJobDescription = review.job_description || currentJobDescription;
  baselineResume = review.resume || baselineResume;

  const jobDescription = el("review-job-description");
  if (jobDescription) {
    jobDescription.textContent = currentJobDescription || "Job description is unavailable for this review.";
  }

  el("review-fit").innerHTML = renderFit(review.result.Fit);
  el("review-gap-map").innerHTML = renderGapMap(review.result.Gap_Map);
  reviewQuestions = getQuestionsForReview(review);
  questionAnswers = Array.isArray(review.answers) ? review.answers : [];
  el("questions-form").innerHTML = renderQuestionsForm(reviewQuestions, questionAnswers);
  el("submit-answers")?.classList.toggle("hidden", reviewQuestions.length === 0);

  if (review.status === "awaiting_answers") {
    el("baseline-resume").textContent = baselineResume || "Resume is unavailable for this review.";
  } else {
    redlineSegments = parseSegments(review.result.Tailored_Resume || "");
    editingIndex = null;
    renderRedlineView();
  }
  renderedReview = review;
}

function onWorkflowRender(state, activeSection) {
  updateDemoToggle(state);
  refreshAuthControls(state);

  if (activeSection !== "review" || !state.review?.result) {
    if (!state.review) {
      renderedReview = null;
      renderReviewTabs(state);
      renderInitialState(state);
    }
    return;
  }

  renderReviewTabs(state);
  if (state.review !== renderedReview) renderReviewContent(state.review);
}

function wireStaticControls() {
  el("demo-toggle").onclick = handleDemoToggle;
  el("submit-review").onclick = handleSubmitReview;
  el("submit-answers").onclick = handleSubmitAnswers;
  el("update-answers").onclick = () => workflow.setActiveTab("questions");
  el("see-proposed-resume").onclick = () => workflow.setActiveTab("resume");
  el("redline-toggle").onchange = renderRedlineView;
  for (const tab of document.querySelectorAll("[data-review-tab]")) {
    tab.onclick = () => workflow.setActiveTab(tab.dataset.reviewTab);
    tab.onkeydown = (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const tabs = [...document.querySelectorAll("[data-review-tab]")];
      const enabledTabs = tabs.filter((candidate) => !candidate.disabled);
      const currentIndex = enabledTabs.indexOf(tab);
      if (currentIndex < 0) return;
      const nextIndex = event.key === "Home"
        ? 0
        : event.key === "End"
          ? enabledTabs.length - 1
          : (currentIndex + (event.key === "ArrowRight" ? 1 : -1) + enabledTabs.length) % enabledTabs.length;
      const nextTab = enabledTabs[nextIndex];
      workflow.setActiveTab(nextTab.dataset.reviewTab);
      nextTab.focus();
    };
  }
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
      baselineResume = null;
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
