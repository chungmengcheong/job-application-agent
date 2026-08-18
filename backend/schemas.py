"""Pydantic contracts for the current review request and response shapes."""
from pydantic import BaseModel, ConfigDict, Field


class Url(BaseModel):
    """A page URL, optionally requesting the canned demo response."""

    url: str  # URL of the page requesting the job description
    demo: bool = False   # if true, return static demo response


class JobListing(BaseModel):
    """A job description to review, optionally requesting the canned demo response."""

    job_description: str  # Job description to be reviewed
    url: str  # URL of calling page for tracking purposes
    demo: bool = False   # if true, return static demo response


class QuestionAnswers(BaseModel):
    """Candidate answers to prior follow-up questions, keyed by question text."""

    qa_pairs: list[dict[str, str]]  # list of question-answer pairs
    demo: bool = False   # if true, return static demo response


class Fit(BaseModel):
    score: int
    rationale: str


class GapItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    jd_requirement_keyword: str = Field(alias="JD Requirement/Keyword")
    present_in_resume: str = Field(alias="Present in Resume?")
    where_evidence: str = Field(alias="Where/Evidence")
    gap_handling: str = Field(alias="Gap handling")


class AnalysisResult(BaseModel):
    """Call 1 output: fit, gaps, and targeted questions. No tailored resume yet."""

    model_config = ConfigDict(populate_by_name=True)

    Fit: Fit
    Gap_Map: list[GapItem]
    Questions: list[str]


class ReviewResult(BaseModel):
    """Call 2 output: revised fit, revised gaps, and the tailored resume."""

    model_config = ConfigDict(populate_by_name=True)

    Fit: Fit
    Gap_Map: list[GapItem]
    Tailored_Resume: str


class SafeError(BaseModel):
    """The stable error shape returned to clients; never includes provider detail."""

    detail: str


class CreateReviewRequest(BaseModel):
    """Body for `POST /api/v1/reviews`. No `resume_id` yet; the resume
    content is submitted inline and stored immutably (Increment 2)."""

    resume: str
    job_description: str
    source_url: str | None = None


class AnswersRequest(BaseModel):
    """Body for `POST /api/v1/reviews/{review_id}/answers`."""

    qa_pairs: list[dict[str, str]]


class ReviewOut(BaseModel):
    """The durable `Review` representation returned by every `/api/v1`
    review route. `result` holds whichever validated shape the review's
    current stage produced (Call 1's fit/gaps/questions, or Call 2's revised
    fit/gaps/tailored resume) and is not re-validated at this layer, since it
    was already validated once before storage."""

    id: str
    status: str
    result: dict | None = None
    safe_error_code: str | None = None
    created_at: str
    updated_at: str
    completed_at: str | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    retryable: bool


class ErrorEnvelope(BaseModel):
    """The one stable `/api/v1` error shape; see backend/errors.py."""

    error: ErrorDetail
