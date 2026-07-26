"""Unit tests for the backend module."""

import pytest
from backend import api
from fastapi.testclient import TestClient
from pathlib import Path
from backend.security import verify_token


# Working files for pytest unit tests
BASE_DIR = Path(__file__).resolve().parent
TEST_RESUME_FILE = BASE_DIR / "user" / "test_resume.txt"
TEST_ADDITIONAL_EXPERIENCE_FILE = BASE_DIR / "user" / "test_additional_experience.txt"
TEST_OUTPUT_FROM_LLM_CURRENT_FILE = BASE_DIR / "temp_stub" / "test_LLM_response_current.json"
TEST_USER_RESPONSE_FILE = BASE_DIR / "temp_stub" / "test_user_response.json"
# Production temp files
TEMP_DIR = BASE_DIR.parent / "temp"
RESUME_BASELINE_FILE = TEMP_DIR / "resume_baseline.txt"
RESUME_REVISED_FILE = TEMP_DIR / "resume_revised.txt"
USER_RESPONSE_FILE = TEMP_DIR / "user_response.json"
OUTPUT_FROM_LLM_PRIOR_FILE = TEMP_DIR / "LLM_response_prior.json"
OUTPUT_FROM_LLM_CURRENT_FILE = TEMP_DIR / "LLM_response_current.json"
JOB_DESCRIPTION_FILE = TEMP_DIR / "job_description.txt"


@pytest.fixture
def test_client(monkeypatch):
    """Create a test client for the FastAPI app."""
    # Patch the verify_token that api.py calls directly
    monkeypatch.setattr(api, "verify_token", lambda creds=None: {
        "sub": "test-user-123",
        "email": "test@example.com",
        "email_verified": True,
        "name": "Test User",
    })

    with TestClient(api.app) as c:
        yield c


def test_init_temp_folder_and_files(test_client):
    """Test that temp folder and files are created."""
    assert TEMP_DIR.exists()
    assert RESUME_BASELINE_FILE.exists()
    assert JOB_DESCRIPTION_FILE.exists()
    assert not OUTPUT_FROM_LLM_CURRENT_FILE.exists()
    assert not OUTPUT_FROM_LLM_PRIOR_FILE.exists()
    assert not RESUME_REVISED_FILE.exists()
    assert not USER_RESPONSE_FILE.exists()


def test_get_job_description(test_client):
    """Test /get_JD endpoint returns (currently demo) job description."""
    response = test_client.post(
        "/jobdescription",
        json={"url": "https://example.com/job"}
    )
    assert response.status_code == 200
    data_dict = response.json()
    # check that content from demo job description file is returned
    assert "CEO/Co-founder" in data_dict["job_description"]


def test_create_resume_diff():
    """Test create_resume_diff creates correct diff output and file."""
    baseline = "This is a text\nThis is a text on a new line"
    revised = "This is a short text\nThis is gibberish on a new line"
    expected_diff = '''This is a<span style="color:#008000"><add> short</add></span> text
This is <span style="color:#c00000"><del>a text</del></span><span style="color:#008000"><add>gibberish</add></span> on a new line'''
    actual_diff = api.create_resume_diff(baseline, revised)
    assert actual_diff == expected_diff


def test_create_review_prompt(monkeypatch):
    """Test prompt template placeholders are replaced and data from previous
     LLM output is read and injected into the prompt."""
    job_description = "This the test job description"
    resume = "This is a test resume"
    additional_experience = "This is a test additional experience"
    rationale = "This is a test rationale"
    question2 = "Question2?"
    answer3 = "Answer3"

    monkeypatch.setattr(api, "RESUME_BASELINE_FILE", TEST_RESUME_FILE)
    monkeypatch.setattr(api, "ADDITIONAL_EXPERIENCE_FILE", TEST_ADDITIONAL_EXPERIENCE_FILE)
    monkeypatch.setattr(api, "OUTPUT_FROM_LLM_CURRENT_FILE", TEST_OUTPUT_FROM_LLM_CURRENT_FILE)
    monkeypatch.setattr(api, "USER_RESPONSE_FILE", TEST_USER_RESPONSE_FILE)
    prompt = api.create_review_prompt(job_description)

    # test that placeholder is replaced with json content
    assert "{{INPUT}}" not in prompt
    # test that user data is read and injected correctly
    assert resume in prompt
    assert additional_experience in prompt
    assert job_description in prompt
    # test that data from previous LLM output is parsed and injected
    assert rationale in prompt
    assert question2 in prompt
    assert answer3 in prompt


def test_generate_review_demo(test_client, monkeypatch):
    """Test /generate/review endpoint returns demo JSON."""
    response = test_client.post(
        "/review",
        json={
            "job_description": "fake job description for demo",
            "save_output": True,
            "url": "https://demo.com/bestjobever",
            "demo": True
        }
    )
    assert response.status_code == 200
    data_dict = response.json()
    assert "Tailored_Resume" in data_dict
    # check that content from demo LLM response file is returned
    assert "Jane Doe" in data_dict["Tailored_Resume"]


def test_generate_review(test_client, monkeypatch):
    """Test /generate/review endpoint parses the LLM response and injects
    a diff resume."""
    def mock_prompt_llm(prompt: str) -> str:
        return TEST_OUTPUT_FROM_LLM_CURRENT_FILE.read_text()
    monkeypatch.setattr(api, "prompt_llm", mock_prompt_llm)

    response = test_client.post(
        "/review",
        json={
            "job_description": "This the test job description",
            "url": "https://example.com/bestjobever",
            "demo": False
        }
    )
    assert response.status_code == 200
    data_dict = response.json()
    # check that content from test LLM response (mock_prompt_llm)file is returned
    assert data_dict["Fit"]["score"] == 10
    assert data_dict["Gap_Map"][1]["JD Requirement/Keyword"] == "Test Requirement1"


def test_process_questions_and_answers_demo(test_client, monkeypatch):
    """Test /questions endpoint creates an updated review off user's answers."""
    response = test_client.post(
        "/questions",
        json={
            "qa_pairs": [
                {"question": "Question1?", "answer": "Answer1"},
                {"question": "Question2?", "answer": "Answer2"}
            ],
            "demo": True
        },
    )
    assert response.status_code == 200
    data_dict = response.json()
    # check that content from demo LLM response file is returned
    assert data_dict["Fit"]["score"] == 8
    assert data_dict["Questions"][0] == "For the ML work at HomeQuest and Financia: what model types/approaches and frameworks were used (e.g., recommenders, NLP, TensorFlow, PyTorch), team size you founded/led, and a measurable outcome (CTR, retention, revenue lift)?"


def test_process_questions_and_answers(test_client, monkeypatch):
    """Test /questions endpoint creates an updated review off user's answers."""
    # TODO: Implement a non-demo test once we have a suitable stubbed LLM response file
    assert False
    return


def test_manage_resume(test_client, monkeypatch):
    """Test /resume endpoint loads and saves resume files."""
    resume = "This is a test resume"
    monkeypatch.setattr(api, "RESUME_FILE", TEST_RESUME_FILE)
    response = test_client.get(
        "/resume",
        params={"command": "load"},
        headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data_dict = response.json()
    # check that content from the test resume file is returned
    assert data_dict["resume"] == resume
