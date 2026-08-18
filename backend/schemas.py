"""Pydantic contracts for the current review response and safe errors."""
from pydantic import BaseModel, ConfigDict, Field


class Fit(BaseModel):
    score: int
    rationale: str


class GapItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    jd_requirement_keyword: str = Field(alias="JD Requirement/Keyword")
    present_in_resume: str = Field(alias="Present in Resume?")
    where_evidence: str = Field(alias="Where/Evidence")
    gap_handling: str = Field(alias="Gap handling")


class ReviewResult(BaseModel):
    """The fit/gaps/questions/tailored-resume shape shared by every review response."""

    model_config = ConfigDict(populate_by_name=True)

    Fit: Fit
    Gap_Map: list[GapItem]
    Questions: list[str]
    Tailored_Resume: str


class SafeError(BaseModel):
    """The stable error shape returned to clients; never includes provider detail."""

    detail: str
