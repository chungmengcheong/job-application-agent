"""The durable `/api/v1` review API (Increment 2).

Mounted from `backend/api.py` at `/api/v1`. Owns only HTTP concerns —
authentication, request validation, and translating `ApiError` into the safe
envelope; `ReviewService` owns the workflow and `ReviewStore` owns
persistence.
"""
from fastapi import FastAPI, Security

from backend.errors import register_error_handlers
from backend.llm_client import LLMClient
from backend.review_service import ReviewService
from backend.review_store import ReviewRecord, ReviewStore
from backend.schemas import AnswersRequest, CreateReviewRequest, ReviewOut
from backend.security import check_authorized_user, security, verify_token

api_v1_app = FastAPI(title="AI Recruiting Agent API v1")
register_error_handlers(api_v1_app)

# Constructs its own LLMClient rather than importing backend.api's, to avoid
# a circular import between the two modules; the constructor is cheap and
# config-driven, so duplicating this one line is not worth abstracting away.
review_store = ReviewStore()
review_service = ReviewService(store=review_store, llm_client=LLMClient())


def _to_review_out(record: ReviewRecord) -> ReviewOut:
    answers = record.answers_json
    if answers is not None:
        questions = [pair.get("question", "") for pair in answers]
    elif record.result_json:
        questions = record.result_json.get("Questions")
    else:
        questions = None
    return ReviewOut(
        id=record.id,
        status=record.status,
        job_description=record.job_description,
        resume=record.resume_content,
        questions=questions,
        answers=answers,
        result=record.result_json,
        safe_error_code=record.safe_error_code,
        created_at=record.created_at,
        updated_at=record.updated_at,
        completed_at=record.completed_at,
    )


@api_v1_app.post("/reviews", response_model=ReviewOut, status_code=201)
def create_review(payload: CreateReviewRequest, creds=Security(security)) -> ReviewOut:
    claims = verify_token(creds)
    check_authorized_user(claims)
    record = review_service.create_review(
        owner=claims["sub"],
        resume_content=payload.resume,
        job_description=payload.job_description,
        source_url=payload.source_url,
    )
    return _to_review_out(record)


@api_v1_app.get("/reviews/{review_id}", response_model=ReviewOut)
def get_review(review_id: str, creds=Security(security)) -> ReviewOut:
    claims = verify_token(creds)
    check_authorized_user(claims)
    record = review_service.get_review(review_id=review_id, owner=claims["sub"])
    return _to_review_out(record)


@api_v1_app.post("/reviews/{review_id}/answers", response_model=ReviewOut)
def submit_answers(
    review_id: str, payload: AnswersRequest, creds=Security(security)
) -> ReviewOut:
    claims = verify_token(creds)
    check_authorized_user(claims)
    record = review_service.submit_answers(
        review_id=review_id, owner=claims["sub"], qa_pairs=payload.qa_pairs
    )
    return _to_review_out(record)
