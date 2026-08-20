// Client-side "routing" is deliberately minimal: hydrate the workspace,
// then check location.pathname for a durable review id and restore it -
// the mechanism the exit gate's "refresh restores a durable review from the
// backend" requires. Demo mode never changes the URL (see docs/frontend.md).
import { getReview } from "./api.js";
import { initBackendModeControl } from "./backend-mode.js";
import { initReviewWorkspace } from "./review-workspace.js";
import * as workflow from "./workflow.js";

const REVIEW_PATH_RE = /^\/app\/reviews\/([^/]+)\/?$/;

async function restoreReviewFromUrl() {
  const match = window.location.pathname.match(REVIEW_PATH_RE);
  if (!match) return;

  const reviewId = decodeURIComponent(match[1]);
  workflow.setState({ demoMode: false, loading: true, error: null });
  try {
    const review = await getReview(reviewId);
    workflow.setState({
      review,
      loading: false,
      activeTab: "job-fit",
      error: review.status === "failed" ? "This review failed. Please start a new one." : null,
    });
  } catch (err) {
    workflow.setState({ loading: false, error: err?.message || "Could not load this review." });
  }

  const heading = document.getElementById("workspace-heading");
  heading?.focus();
}

async function bootstrap() {
  await initBackendModeControl();
  await initReviewWorkspace();
  await restoreReviewFromUrl();
}

document.addEventListener("DOMContentLoaded", bootstrap);
