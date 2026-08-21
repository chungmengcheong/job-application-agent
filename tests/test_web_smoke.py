"""Production-like browser smoke test for the supported web client (web/).

Starts the real FastAPI app (`uvicorn backend.api:app`) on a throwaway port
and drives a real browser through the full two-call demo flow - the same
`web/` files and same app that serve production, not a dev-only shortcut.
Needs no live credentials or provider call, since the demo path never
reaches the model.

Dev-only: requires `pip install -r requirements-dev.txt` and
`playwright install chromium`, neither of which are runtime dependencies of
the deployed app. Skips cleanly if playwright isn't installed.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

playwright_sync_api = pytest.importorskip("playwright.sync_api")

REPO_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    """Runs the real app in a subprocess against an isolated throwaway database."""
    port = _free_port()
    db_dir = tempfile.mkdtemp(prefix="web-smoke-db-")
    env = {
        "REVIEWS_DB_PATH": str(Path(db_dir) / "reviews.db"),
        "ENVIRONMENT": "development",
        "PATH": os.environ.get("PATH", ""),
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api:app", "--port", str(port)],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base_url)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def _wait_for_server(base_url: str, timeout: float = 15.0) -> None:
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{base_url}/health", timeout=1)
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.2)
    raise RuntimeError(f"Server at {base_url} did not become healthy in time.")


def test_splash_page_uses_new_brand_and_preserves_future_features(live_server, page) -> None:
    """The public splash page carries the renamed brand while retaining
    interest-testing for the unimplemented application and networking features.
    """
    page.goto(live_server)

    assert page.title() == "Job Application Coach — Get Interviews Faster"
    assert "Job Application Coach" in page.locator("body").inner_text()
    assert page.get_by_text("Agentic Form Completion").is_visible()
    assert page.get_by_text("Networking Intelligence").is_visible()
    assert not page.get_by_text("Get Chrome extension").is_visible()


def test_demo_review_and_answers_flow_renders_end_to_end(live_server, page) -> None:
    """Submits the demo job description, answers the follow-up questions,
    and confirms fit/gaps/questions render after Call 1 and the tailored
    resume/redline renders after Call 2 - all through the actual served
    web/ files and the actual FastAPI app, no live provider call."""
    page.goto(f"{live_server}/app/")

    page.locator("#api-mode-toggle").wait_for(state="visible")
    job_description_field = page.locator("#job-description")
    job_description_field.wait_for(state="visible")
    # Demo mode prefills the job description from the canned fixture.
    page.wait_for_function(
        "document.getElementById('job-description').value.length > 0"
    )

    assert page.locator("#section-review").is_visible()
    assert page.locator("#tab-job-description").get_attribute("aria-selected") == "true"
    assert page.locator("#tab-job-fit").is_disabled()
    assert page.locator("#tab-questions").is_disabled()
    assert not page.locator("#tab-resume").is_disabled()
    page.click("#tab-resume")
    page.wait_for_function(
        "document.getElementById('baseline-resume').textContent.trim().length > 0"
    )
    assert page.locator("#baseline-resume").inner_text().strip() != ""
    assert "\n" in page.locator("#baseline-resume").text_content()
    page.click("#tab-job-description")

    page.click("#submit-review")

    page.locator("#section-review").wait_for(state="visible", timeout=20_000)
    page.click("#tab-questions")
    page.locator(".question-item textarea").first.wait_for(state="visible", timeout=20_000)
    assert page.locator("#tab-job-fit").inner_text().strip() == "Job fit"
    assert page.locator("#tab-questions").inner_text().strip() == "Questions for You"
    assert page.locator("#tab-resume").inner_text().strip() == "Resume"
    assert page.locator("#answer-0").input_value().strip() != ""
    assert page.locator("#review-fit .fit-badge").inner_text().strip() != ""
    assert page.locator(".gap-card").count() > 0
    assert page.locator("#review-job-description").inner_text().strip() != ""

    assert "Additional Information from you" in page.locator("#questions-form").inner_text()
    assert page.locator(".question-item textarea").count() > 0
    page.click("#tab-job-fit")
    assert page.locator("#job-fit-actions").is_visible()
    assert page.locator("#update-answers").inner_text().strip() == "Provide answers to questions"
    assert page.locator("#see-proposed-resume").is_disabled()
    page.click("#update-answers")
    assert page.locator("#tab-questions").get_attribute("aria-selected") == "true"
    page.fill(".question-item textarea >> nth=0", "Extra relevant detail for the demo.")
    page.click("#submit-answers")

    page.locator("#section-review").wait_for(state="visible", timeout=20_000)
    assert page.locator("#tab-job-fit").inner_text().strip() == "Revised Job Fit"
    assert page.locator("#tab-questions").inner_text().strip() == "Questions for You"
    assert page.locator("#tab-resume").inner_text().strip() == "Proposed resume"
    assert page.locator("#update-answers").inner_text().strip() == "Update answers to questions"
    assert not page.locator("#see-proposed-resume").is_disabled()
    assert page.locator("#review-fit .fit-badge").inner_text().strip() != ""
    page.click("#see-proposed-resume")
    assert page.locator("#tab-resume").get_attribute("aria-selected") == "true"
    page.click("#tab-questions")
    assert page.locator("#answer-0").input_value() == "Extra relevant detail for the demo."
    page.fill("#answer-0", "Updated detail for the demo.")
    page.click("#submit-answers")
    page.locator("#tab-questions").wait_for(state="visible", timeout=20_000)
    assert page.locator("#tab-job-fit").inner_text().strip() == "Revised Job Fit"
    page.click("#tab-questions")
    assert page.locator("#answer-0").input_value() == "Updated detail for the demo."
    page.click("#tab-resume")
    assert page.locator("#redline-container").inner_text().strip() != ""


def test_reviews_url_restores_a_durable_review_on_load(live_server, page) -> None:
    """A fresh page load at /app/reviews/{id} must hydrate from
    `GET /api/v1/reviews/{id}`, not from memory - the exit-gate behavior
    itself. Live Google OAuth is out of scope here (Increment 4's job - see
    backlog.md); this seeds a stored token and intercepts just the one
    `/api/v1/reviews/{id}` call to exercise the real main.js/workflow.js/
    review-display.js/redline.js restoration path end-to-end.
    """
    page.add_init_script(
        """
        localStorage.setItem(
          "ai_recruiting_agent_auth",
          JSON.stringify({accessToken: "a", idToken: "header.eyJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20ifQ.sig", expiresAt: Date.now() + 60000})
        );
        """
    )

    review_body = {
        "id": "rev_smoketest",
        "status": "completed",
        "job_description": "Restored job description.",
        "resume": "Restored baseline resume.",
        "questions": ["What else?"],
        "answers": [{"question": "What else?", "answer": "Restored answer."}],
        "result": {
            "Fit": {"score": 8, "rationale": "Restored rationale."},
            "Gap_Map": [
                {
                    "JD Requirement/Keyword": "Leadership",
                    "Present in Resume?": "Y",
                    "Where/Evidence": "Led a team.",
                    "Gap handling": "Retain evidence.",
                }
            ],
            "Tailored_Resume": 'Summary <span style="color:#008000"><add>improved</add></span> text.',
        },
        "safe_error_code": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:00:01Z",
    }
    page.route(
        "**/api/v1/reviews/rev_smoketest",
        lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(review_body)),
    )

    page.goto(f"{live_server}/app/reviews/rev_smoketest")

    page.locator("#section-review").wait_for(state="visible", timeout=10_000)
    page.locator("#review-fit .fit-badge").wait_for(state="visible", timeout=10_000)
    assert page.evaluate("document.activeElement.id") == "workspace-heading"
    assert page.locator("#tab-job-fit").inner_text().strip() == "Revised Job Fit"
    assert "8/10" in page.locator("#review-fit .fit-badge").inner_text()
    page.click("#tab-job-description")
    assert "Restored job description." in page.locator("#review-job-description").inner_text()
    page.click("#tab-questions")
    assert page.locator("#answer-0").input_value() == "Restored answer."
    page.click("#tab-resume")
    assert "improved" in page.locator("#redline-container").inner_text()


def test_splash_page_links_to_the_web_app(live_server, page) -> None:
    page.goto(live_server)
    assert page.locator('a[href="/app/"]').first.is_visible()
