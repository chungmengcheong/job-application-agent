"""Filesystem locations for demo fixtures, prompt templates, and the one
operator resume/database.

These are fixed relative to the repo layout, not environment configuration
- see backend/config.py for values that vary by deployment.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

USER_DIR = REPO_ROOT / "user"
DEMO_DIR = REPO_ROOT / "demo"
TEMP_DIR = REPO_ROOT / "temp"
STATIC_DIR = REPO_ROOT / "static"
WEB_DIR = REPO_ROOT / "web"
PROMPTS_DIR = REPO_ROOT / "prompts"
DATA_DIR = REPO_ROOT / "data"

# The one operator resume, until Increment 3.5 introduces per-user stored resumes.
RESUME_FILE = USER_DIR / "resume.txt"
ADDITIONAL_EXPERIENCE_FILE = USER_DIR / "additional_candidate_info.txt"

# demo_maker.py's temp working files
RESUME_BASELINE_FILE = TEMP_DIR / "resume_baseline.txt"
RESUME_REVISED_FILE = TEMP_DIR / "resume_revised.txt"
USER_RESPONSE_FILE = TEMP_DIR / "user_response.json"
OUTPUT_FROM_LLM_PRIOR_FILE = TEMP_DIR / "LLM_response_prior.json"
OUTPUT_FROM_LLM_CURRENT_FILE = TEMP_DIR / "LLM_response_current.json"

# Demo fixtures
RESUME_DEMO_FILE = DEMO_DIR / "resume_demo.txt"
JOB_DESCRIPTION_DEMO_FILE = DEMO_DIR / "job_description_demo.txt"
RESPONSE_REVIEW_ADD_INFO_DEMO_FILE = DEMO_DIR / "API_response_review_add_info_demo.json"
RESPONSE_REVIEW_DEMO_FILE = DEMO_DIR / "API_response_review_demo.json"

# Prompt templates
PROMPT_CALL1_ANALYSIS_FILE = PROMPTS_DIR / "prompt_call1_analysis_GOLD.txt"
PROMPT_CALL2_TAILOR_FILE = PROMPTS_DIR / "prompt_call2_tailor_GOLD.txt"

# Reviews database
DEFAULT_DB_PATH = DATA_DIR / "reviews.db"
