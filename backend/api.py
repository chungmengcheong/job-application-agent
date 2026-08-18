"""Backend APIs for generating a resume review and redlines against a job listing."""

from fastapi import FastAPI, Security, HTTPException, status, Response
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pydantic import ValidationError
from langsmith import traceable, Client
from pathlib import Path
import os, shutil, datetime
import json
from dotenv import load_dotenv
from backend.llm_client import LLMClient
from backend.redline import redline_diff
from backend.schemas import AnalysisResult, JobListing, QuestionAnswers, ReviewResult, Url
from backend.security import check_authorized_user, verify_token, security
from backend.security import router as oauth_router

# Load environment variables from .env file
REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=False)

# Define the directory paths for working files
BASE_DIR = Path(__file__).resolve().parent.parent
USER_DIR = BASE_DIR / "user"
PROMPT_DIR = BASE_DIR / "prompts"
TEMP_DIR = BASE_DIR / "temp"
DEMO_DIR = BASE_DIR / "demo"
STATIC_DIR = BASE_DIR / "static"
# User data
RESUME_FILE = USER_DIR / "resume.txt"
ADDITIONAL_EXPERIENCE_FILE = USER_DIR / "additional_candidate_info.txt"
# Prompt templates
PROMPT_CALL1_ANALYSIS_FILE = PROMPT_DIR / "prompt_call1_analysis_GOLD.txt"
PROMPT_CALL2_TAILOR_FILE = PROMPT_DIR / "prompt_call2_tailor_GOLD.txt"
# Temp working files
RESUME_BASELINE_FILE = TEMP_DIR / "resume_baseline.txt"
RESUME_REVISED_FILE = TEMP_DIR / "resume_revised.txt"
USER_RESPONSE_FILE = TEMP_DIR / "user_response.json"
OUTPUT_FROM_LLM_PRIOR_FILE = TEMP_DIR / "LLM_response_prior.json"
OUTPUT_FROM_LLM_CURRENT_FILE = TEMP_DIR / "LLM_response_current.json"
JOB_DESCRIPTION_FILE = TEMP_DIR / "job_description.txt"
# Demo files
RESUME_DEMO_FILE = DEMO_DIR / "resume_demo.txt"
JOB_DESCRIPTION_DEMO_FILE = DEMO_DIR / "job_description_demo.txt"
RESPONSE_REVIEW_ADD_INFO_DEMO_FILE = DEMO_DIR / "API_response_review_add_info_demo.json"
RESPONSE_REVIEW_DEMO_FILE = DEMO_DIR / "API_response_review_demo.json"

print(f"{datetime.datetime.now()} starting up API server...")

# The active provider/model is config-driven; see backend/llm_client.py.
llm_client = LLMClient()

# Setup development tracing. Production can disable tracing by setting
# LANGSMITH_TRACING_V2=false before the process starts.
os.environ.setdefault("LANGSMITH_TRACING_V2", "true")
os.environ.setdefault("LANGCHAIN_PROJECT", "AIRecruitingAgent")
langsmith_client = Client(api_key=os.getenv("LANGSMITH_API_KEY"))

# ENVIRONMENT gates debug behavior. Default to development so a missing
# variable fails toward verbose local debugging rather than a silent
# production misconfiguration.
ENVIRONMENT = (os.getenv("ENVIRONMENT") or "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# Prepare temp and working files for FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Setup temp working directory on startup."""
    ## startup items
    # make temp directory
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    # copy the user's saved resume.txt into temp directory as the baseline
    shutil.copyfile(RESUME_DEMO_FILE, RESUME_BASELINE_FILE)
    # Make the demo job description the working job description
    shutil.copyfile(JOB_DESCRIPTION_DEMO_FILE, JOB_DESCRIPTION_FILE)
    # delete each stale temp working file independently, so one missing file
    # does not stop cleanup of the rest
    for stale_file in (
        OUTPUT_FROM_LLM_CURRENT_FILE,
        RESUME_REVISED_FILE,
        USER_RESPONSE_FILE,
        OUTPUT_FROM_LLM_PRIOR_FILE,
    ):
        stale_file.unlink(missing_ok=True)
    yield
    ## cleanup items here
    # none for now

# setup FastAPI app with CORS; mount oauth_router and static files
app = FastAPI(debug=not IS_PRODUCTION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Chrome extension
        "chrome-extension://oblgighcolckndbinadplmmmebjemido",
        # Vercel deployed frontend
        "https://ai-recruiting-agent.vercel.app",
        # Local Next.js dev server (two variants to be safe)
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Mount the callback rounter /oauth2cb
app.include_router(oauth_router)
# Serve static files at /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def splash():
    """Serve the marketing splash page."""
    return FileResponse(STATIC_DIR / "index.html")


@traceable(name="prompt_LLM")
def prompt_llm(prompt: str) -> str:
    """Call the configured LLM to get a response."""
    return llm_client.complete(prompt)


def create_call1_prompt(job_description: str) -> str:
    """Construct JSON input and inject into the Call 1 (analysis and questions) prompt."""
    input_dict = {
        "Job_Description": job_description,
        "Resume": RESUME_BASELINE_FILE.read_text(),
    }
    if ADDITIONAL_EXPERIENCE_FILE.exists():
        input_dict["Additional_Info"] = ADDITIONAL_EXPERIENCE_FILE.read_text()

    input_json = json.dumps(input_dict, indent=4)
    prompt = PROMPT_CALL1_ANALYSIS_FILE.read_text()
    return prompt.replace("{{INPUT}}", input_json)


def create_call2_prompt(job_description: str, qa_pairs: list[dict]) -> str:
    """Construct JSON input and inject into the Call 2 (revised analysis and
    tailored resume) prompt. Carries forward Call 1's fit and gaps, the same
    resume and job description, and the candidate's answers.
    """
    input_dict = {
        "Job_Description": job_description,
        "Resume": RESUME_BASELINE_FILE.read_text(),
    }
    if ADDITIONAL_EXPERIENCE_FILE.exists():
        input_dict["Additional_Info"] = ADDITIONAL_EXPERIENCE_FILE.read_text()
    if OUTPUT_FROM_LLM_CURRENT_FILE.exists():
        call1_response = json.loads(OUTPUT_FROM_LLM_CURRENT_FILE.read_text())
        input_dict["Fit"] = call1_response.get("Fit")
        input_dict["Gap_Map"] = call1_response.get("Gap_Map")
    input_dict["qa_pairs"] = qa_pairs

    input_json = json.dumps(input_dict, indent=4)
    prompt = PROMPT_CALL2_TAILOR_FILE.read_text()
    return prompt.replace("{{INPUT}}", input_json)


def create_resume_diff(baseline:str, revised:str) -> str:
    """Create a redlined diff between two resume versions."""
    return redline_diff(baseline, revised)


@app.get("/health")
def show_heartbeat():
    """Return a message to show API is up."""
    return {"message": "Hello World"}


@app.post("/jobdescription")
def get_job_description_from_url(url:Url):
    """Fetch job description from URL."""
    # TODO: Implement logic to fetch job description based on URL vs. demo JD
    if url.demo:
        # demo reads its own fixture; it must never read the live temp/ state
        job_description = JOB_DESCRIPTION_DEMO_FILE.read_text()
        return {"job_description": job_description}

    # For now, always return the demo JD when not implemented.
    job_description = JOB_DESCRIPTION_FILE.read_text()
    return {"job_description": job_description}


def _call_llm_and_validate(prompt: str, schema: type, call_name: str):
    """Call the LLM and validate its complete output before it can replace any
    prior valid state. Returns the validated result and the raw response text.
    """
    print(f"{datetime.datetime.now()}: calling the LLM with prompt length", len(prompt))
    try:
        llm_response_json = prompt_llm(prompt)
    except Exception as e:
        print(f"{call_name}: LLM call failed:", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{call_name}: LLM call failed. Please try again."
        )

    try:
        result = schema.model_validate(json.loads(llm_response_json))
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"{call_name}: invalid model output:", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{call_name}: model returned an invalid response. Try again."
        )

    return result, llm_response_json


def _rotate_llm_output(llm_response_json: str) -> None:
    """Keep the last two raw LLM responses, so Call 2 can read Call 1's output."""
    if OUTPUT_FROM_LLM_CURRENT_FILE.exists():
        os.replace(OUTPUT_FROM_LLM_CURRENT_FILE, OUTPUT_FROM_LLM_PRIOR_FILE)
    OUTPUT_FROM_LLM_CURRENT_FILE.write_text(llm_response_json)


@app.post("/review", response_model=AnalysisResult)
@traceable(name="generate_review_endpoint")
def generate_review(job_listing: JobListing,
                    creds=Security(security)
                    ):
    """Run Call 1: analysis and questions only.
    Algo:
    1. If demo is true, return canned response
    2. Create the Call 1 prompt from the resume and job description
    3. Call the LLM and validate fit, gaps, and questions
    4. Save the raw response to OUTPUT_FROM_LLM_CURRENT_FILE for Call 2 to read
    5. Return the response

    Call 1 deliberately does not generate a tailored resume.
    """
    if job_listing.demo:  # returned stubbed API response
        response = json.loads(RESPONSE_REVIEW_DEMO_FILE.read_text())
        return response

    # authenticate/authorize
    claims = verify_token(creds)
    check_authorized_user(claims)

    # persist the submitted job description so Call 2 reuses the same input
    JOB_DESCRIPTION_FILE.write_text(job_listing.job_description)

    prompt = create_call1_prompt(job_listing.job_description)
    result, llm_response_json = _call_llm_and_validate(
        prompt, AnalysisResult, "generate_review"
    )

    _rotate_llm_output(llm_response_json)

    return result.model_dump(by_alias=True)


@app.post("/questions", response_model=ReviewResult)
@traceable(name="process_questions_and_answers_endpoint")
def process_questions_and_answers(user_response: QuestionAnswers,
                                  creds=Security(security)
                                  ):
    """Run Call 2: revised analysis and tailored resume.
    Algo:
    1. If demo is true, return canned response
    2. Save the candidate's answers to USER_RESPONSE_FILE
    3. Create the Call 2 prompt from the same resume, same job description,
       Call 1's fit/gaps, and the answers
    4. Call the LLM and validate revised fit, revised gaps, and the tailored resume
    5. Save the revised resume and return its diff against the baseline
    """
    # return stubbed response for demo
    if user_response.demo:
        response = json.loads(RESPONSE_REVIEW_ADD_INFO_DEMO_FILE.read_text())
        return response

    # authenticate/authorize before proceeding
    claims = verify_token(creds)
    check_authorized_user(claims)

    # save the candidate's answers
    qa_pairs = user_response.qa_pairs
    USER_RESPONSE_FILE.write_text(json.dumps(qa_pairs, indent=4))

    # Call 2 reuses the same job description Call 1 persisted, not a resubmission
    job_description = JOB_DESCRIPTION_FILE.read_text()
    prompt = create_call2_prompt(job_description, qa_pairs)
    result, llm_response_json = _call_llm_and_validate(
        prompt, ReviewResult, "process_questions_and_answers"
    )

    _rotate_llm_output(llm_response_json)

    # diff the baseline and revised resumes, and save the diff in the API response
    revised_resume = result.Tailored_Resume
    RESUME_REVISED_FILE.write_text(revised_resume)  # save revised resume
    baseline_resume = RESUME_BASELINE_FILE.read_text()
    response = result.model_dump(by_alias=True)
    response["Tailored_Resume"] = create_resume_diff(baseline_resume, revised_resume)

    return response


@app.get("/resume")
def manage_resume(command: str, demo: bool = False,
                  creds = Security(security),
                  ):
    """Return the user's saved resume."""
    # return stubbed response for demo (no auth required for demo); read-only,
    # must never touch the live baseline shared with the live workflow
    if demo:
        return {"resume": RESUME_DEMO_FILE.read_text()}

    # If not in demo and no credentials provided, avoid 401 spam and return a clear error
    if not creds:
        return {"error": "Authentication required to load resume."}

    # authenticate/authorize before proceeding
    claims = verify_token(creds)
    check_authorized_user(claims)

    if command == "load":
        shutil.copyfile(RESUME_FILE, RESUME_BASELINE_FILE)
        response = {"resume": RESUME_FILE.read_text()}
    else:
        response = {"error": "Invalid command"}
    return response
