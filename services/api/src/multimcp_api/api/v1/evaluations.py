"""RAG evaluation enqueue and status (SPEC §6.3 / §8)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from multimcp_api.auth import require_ingest_token
from multimcp_api.deps import get_app_settings, get_repository
from multimcp_api.domain.models import EvalJob
from multimcp_api.errors import AppError
from multimcp_api.eval.judge import JudgeClient, OpenAIJudgeClient
from multimcp_api.eval.runner import run_eval_job
from multimcp_api.repositories.base import EventRepository
from multimcp_api.schemas.eval import (
    EvaluationAcceptedResponse,
    EvaluationCreateRequest,
    EvaluationJobResponse,
)
from multimcp_api.settings import Settings

router = APIRouter(tags=["evaluations"], dependencies=[Depends(require_ingest_token)])

JudgeFactory = Callable[[Settings], JudgeClient]


def default_judge_factory(settings: Settings) -> JudgeClient:
    return OpenAIJudgeClient(
        model=settings.judge_model,
        api_key=settings.judge_api_key,
        base_url=settings.judge_base_url,
    )


@router.post(
    "/evaluations",
    response_model=EvaluationAcceptedResponse,
    status_code=202,
)
async def create_evaluation(
    payload: EvaluationCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    repository: Annotated[EventRepository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> EvaluationAcceptedResponse:
    job = EvalJob(
        rubric_version=payload.rubric_version,
        trace_id=payload.trace_id,
        query=payload.query,
        contexts=payload.contexts,
        answer=payload.answer,
        judge_model=settings.judge_model or None,
    )
    await repository.enqueue_eval(job)
    if settings.eval_backend == "inline":
        factory: JudgeFactory = getattr(
            request.app.state, "judge_factory", default_judge_factory
        )
        background_tasks.add_task(
            _run_inline,
            repository,
            factory(settings),
            settings.judge_model or None,
            job.job_id,
        )
    return EvaluationAcceptedResponse(job_id=job.job_id)


@router.get("/evaluations/{job_id}", response_model=EvaluationJobResponse)
async def get_evaluation(
    job_id: UUID,
    repository: Annotated[EventRepository, Depends(get_repository)],
) -> EvaluationJobResponse:
    job = await repository.get_eval(job_id)
    if job is None:
        raise AppError(404, "not_found", f"evaluation {job_id} not found")
    data = job.model_dump(exclude={"locked_at"})
    return EvaluationJobResponse.model_validate({"schema_version": "1.0", **data})


async def _run_inline(
    repository: EventRepository,
    judge: JudgeClient,
    judge_model: str | None,
    job_id: UUID,
) -> None:
    started = await repository.start_eval(job_id, lock_seconds=300)
    if started is None:
        return
    await run_eval_job(repository, judge, job_id, judge_model=judge_model)
