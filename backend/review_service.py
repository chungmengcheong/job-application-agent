"""`ReviewService` owns the durable two-call workflow: it builds each call's
prompt from the review's own immutable, stored inputs (never global files),
validates the provider's output before persisting it, and maps failures to
the safe `/api/v1` error envelope.
"""
import json
import logging
from pathlib import Path

from fastapi import status
from langsmith import traceable
from pydantic import ValidationError

from backend.errors import ApiError
from backend.llm_client import LLMClient
from backend.paths import PROMPT_CALL1_ANALYSIS_FILE, PROMPT_CALL2_TAILOR_FILE
from backend.redline import redline_diff
from backend.review_store import ReviewRecord, ReviewStore
from backend.schemas import AnalysisResult, ReviewResult


logger = logging.getLogger(__name__)


class ReviewService:
    """Runs Call 1 and Call 2 against a durable `Review` record."""

    def __init__(
        self,
        store: ReviewStore,
        llm_client: LLMClient,
        *,
        call1_prompt_path: Path = PROMPT_CALL1_ANALYSIS_FILE,
        call2_prompt_path: Path = PROMPT_CALL2_TAILOR_FILE,
    ) -> None:
        self._store = store
        self._llm_client = llm_client
        self._call1_prompt_path = call1_prompt_path
        self._call2_prompt_path = call2_prompt_path

    @staticmethod
    def _build_call1_prompt(prompt_path: Path, resume_content: str, job_description: str) -> str:
        input_dict = {"Job_Description": job_description, "Resume": resume_content}
        input_json = json.dumps(input_dict, indent=4)
        return prompt_path.read_text().replace("{{INPUT}}", input_json)

    @staticmethod
    def _build_call2_prompt(
        prompt_path: Path,
        resume_content: str,
        job_description: str,
        call1_result: dict | None,
        qa_pairs: list[dict],
    ) -> str:
        input_dict = {"Job_Description": job_description, "Resume": resume_content}
        if call1_result:
            input_dict["Fit"] = call1_result.get("Fit")
            input_dict["Gap_Map"] = call1_result.get("Gap_Map")
        input_dict["qa_pairs"] = qa_pairs
        input_json = json.dumps(input_dict, indent=4)
        return prompt_path.read_text().replace("{{INPUT}}", input_json)

    def _complete_and_validate(self, prompt: str, schema: type, call_name: str):
        try:
            raw = self._llm_client.complete(prompt)
        except Exception as error:
            # Keep the client-facing envelope deliberately generic, but make
            # provider failures diagnosable in the deployment log. Do not log
            # the prompt, resume, job description, answers, or credentials.
            logger.exception(
                "LLM call failed: call=%s exception=%s status_code=%s request_id=%s",
                call_name,
                type(error).__name__,
                getattr(error, "status_code", None),
                getattr(error, "request_id", None),
            )
            raise ApiError(
                code="MODEL_CALL_FAILED",
                message=f"{call_name}: the model call failed. Please try again.",
                status_code=status.HTTP_502_BAD_GATEWAY,
                retryable=True,
            )
        try:
            return schema.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError):
            raise ApiError(
                code="MODEL_INVALID_OUTPUT",
                message=f"{call_name}: the model returned an invalid response. Please try again.",
                status_code=status.HTTP_502_BAD_GATEWAY,
                retryable=True,
            )

    @traceable(name="review_service.create_review")
    def create_review(
        self,
        *,
        owner: str,
        resume_content: str,
        job_description: str,
        source_url: str | None,
    ) -> ReviewRecord:
        record = self._store.create(
            owner=owner,
            resume_content=resume_content,
            job_description=job_description,
            source_url=source_url,
        )
        prompt = self._build_call1_prompt(
            self._call1_prompt_path, resume_content, job_description
        )
        try:
            result = self._complete_and_validate(prompt, AnalysisResult, "create_review")
        except ApiError as error:
            self._store.mark_failed(record.id, error.code)
            raise
        self._store.mark_awaiting_answers(record.id, result.model_dump(by_alias=True))
        return self._store.get(record.id)

    @traceable(name="review_service.submit_answers")
    def submit_answers(
        self, *, review_id: str, owner: str, qa_pairs: list[dict]
    ) -> ReviewRecord:
        record = self.get_review(review_id=review_id, owner=owner)
        if record.status not in {"awaiting_answers", "completed", "failed"} or record.result_json is None:
            raise ApiError(
                code="REVIEW_NOT_AWAITING_ANSWERS",
                message="This review is not ready for answers.",
                status_code=status.HTTP_409_CONFLICT,
            )

        prompt = self._build_call2_prompt(
            self._call2_prompt_path,
            record.resume_content,
            record.job_description,
            record.result_json,
            qa_pairs,
        )
        try:
            result = self._complete_and_validate(prompt, ReviewResult, "submit_answers")
        except ApiError as error:
            self._store.mark_failed(record.id, error.code, answers_json=qa_pairs)
            raise

        result_dict = result.model_dump(by_alias=True)
        result_dict["Tailored_Resume"] = redline_diff(
            record.resume_content, result.Tailored_Resume
        )
        self._store.mark_completed(record.id, result_dict, qa_pairs)
        return self._store.get(record.id)

    def get_review(self, *, review_id: str, owner: str) -> ReviewRecord:
        record = self._store.get_for_owner(review_id, owner)
        if record is None:
            raise ApiError(
                code="NOT_FOUND",
                message="Review not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record
