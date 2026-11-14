"""Shared eval execution for inline BackgroundTasks and the Postgres worker."""

from __future__ import annotations

import logging
from uuid import UUID

from multimcp_api.domain.models import EvalOutcome
from multimcp_api.eval.judge import JudgeClient
from multimcp_api.repositories.base import EventRepository

logger = logging.getLogger("multimcp_api.eval")
MAX_ATTEMPTS = 3


async def run_eval_job(
    repository: EventRepository,
    judge: JudgeClient,
    job_id: UUID,
    *,
    judge_model: str | None = None,
) -> None:
    job = await repository.get_eval(job_id)
    if job is None:
        logger.error("eval job %s not found", job_id)
        return
    try:
        verdict = await judge.judge(
            query=job.query, contexts=job.contexts, answer=job.answer
        )
        await repository.complete_eval(
            job_id,
            EvalOutcome(
                status="succeeded",
                context_relevance=verdict.context_relevance,
                hallucination_label=verdict.hallucination_label,
                rationale=verdict.rationale,
                judge_model=judge_model,
            ),
        )
    except Exception as exc:
        logger.exception("eval job %s failed on attempt %s", job_id, job.attempt)
        if job.attempt >= MAX_ATTEMPTS:
            await repository.complete_eval(
                job_id,
                EvalOutcome(
                    status="failed",
                    error_message=str(exc)[:500],
                    judge_model=judge_model,
                ),
            )
        else:
            await repository.requeue_eval(job_id)
