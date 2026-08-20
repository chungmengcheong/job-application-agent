"""Backend APIs for generating a resume review and redlines against a job listing.

The durable, authenticated live workflow lives under `/api/v1` (see
`backend/api_v1.py`); the routes in this module now serve only the permanent
canned demo (no LLM call, no persistence, no `temp/` dependency) plus a
minimal resume-text getter that the live client uses to submit resume content
inline.
"""

import datetime
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Security
from fastapi.responses import FileResponse
from langsmith import Client
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from backend.api_v1 import api_v1_app
from backend.config import settings
from backend.db import init_db
from backend.paths import (
    JOB_DESCRIPTION_DEMO_FILE,
    RESPONSE_REVIEW_ADD_INFO_DEMO_FILE,
    RESPONSE_REVIEW_DEMO_FILE,
    RESUME_DEMO_FILE,
    RESUME_FILE,
    STATIC_DIR,
    WEB_DIR,
)
from backend.schemas import (
    AnalysisResult,
    JobListing,
    QuestionAnswers,
    ReviewResult,
    Url,
)
from backend.security import check_authorized_user, security, verify_token
from backend.security import router as oauth_router

print(f"{datetime.datetime.now()} starting up API server...")

# Setup development tracing. Production can disable tracing by setting
# LANGSMITH_TRACING_V2=false before the process starts. The @traceable
# decorator (backend/review_service.py) reads LANGSMITH_API_KEY from
# os.environ directly for its own default client, not from settings.
os.environ.setdefault("LANGSMITH_TRACING_V2", str(settings.langsmith_tracing_v2).lower())
os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
langsmith_client = Client(api_key=settings.langsmith_api_key or None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure the reviews database exists on startup."""
    init_db()
    yield


# setup FastAPI app with CORS; mount oauth_router, /api/v1, and static files
app = FastAPI(debug=not settings.is_production, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Chrome extension
        f"chrome-extension://{settings.chrome_extension_id}",
        # Deployed frontend + local dev origins
        *settings.cors_origins,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Mount the callback rounter /oauth2cb
app.include_router(oauth_router)
# Mount the durable, authenticated review API
app.mount("/api/v1", api_v1_app)
# Serve static files at /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def splash():
    """Serve the marketing splash page."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/app/reviews/{review_id}", include_in_schema=False)
def web_review_page(review_id: str):
    """Serve the one web app document for a durable-review URL.

    Registered before the /app static mount below, since a static file mount
    alone 404s on a path with no matching file. web/js/main.js reads the
    review id back out of location.pathname client-side.
    """
    return FileResponse(WEB_DIR / "index.html")


# Serve the supported web client at /app (plain HTML/CSS/JS, no build step).
# html=True serves index.html automatically for /app/ and its subpaths.
app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="web")


@app.get("/health")
def show_heartbeat():
    """Return a message to show API is up."""
    return {"message": "Hello World"}


@app.post("/jobdescription")
def get_job_description_from_url(url: Url):
    """Return the demo-seeded job description. Real URL extraction is not
    implemented; the live client pastes the job description directly and
    does not call this route.
    """
    if url.demo:
        # demo reads its own fixture; it must never read live state
        job_description = JOB_DESCRIPTION_DEMO_FILE.read_text()
        return {"job_description": job_description}

    return {"job_description": ""}


@app.post("/review", response_model=AnalysisResult)
def generate_review(job_listing: JobListing):
    """Return the canned Call 1 demo response.

    The live Call 1 workflow is `POST /api/v1/reviews`; this route now only
    serves the permanent canned demo.
    """
    response = json.loads(RESPONSE_REVIEW_DEMO_FILE.read_text())
    return response


@app.post("/questions", response_model=ReviewResult)
def process_questions_and_answers(user_response: QuestionAnswers):
    """Return the canned Call 2 demo response.

    The live Call 2 workflow is `POST /api/v1/reviews/{review_id}/answers`;
    this route now only serves the permanent canned demo.
    """
    response = json.loads(RESPONSE_REVIEW_ADD_INFO_DEMO_FILE.read_text())
    return response


@app.get("/resume")
def manage_resume(command: str, demo: bool = False,
                  creds = Security(security),
                  ):
    """Return the demo resume, or (authenticated) the one operator resume's
    text, so the live client can submit it inline to `POST /api/v1/reviews`.
    """
    if demo:
        return {"resume": RESUME_DEMO_FILE.read_text()}

    if not creds:
        return {"error": "Authentication required to load resume."}

    claims = verify_token(creds)
    check_authorized_user(claims)

    if command == "load":
        response = {"resume": RESUME_FILE.read_text()}
    else:
        response = {"error": "Invalid command"}
    return response
