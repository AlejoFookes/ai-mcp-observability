"""Postgres eval worker: python -m multimcp_api.eval.worker"""

from __future__ import annotations

import asyncio
import logging
import os

from multimcp_api.eval.judge import OpenAIJudgeClient
from multimcp_api.eval.runner import run_eval_job
from multimcp_api.repositories.factory import build_repository
from multimcp_api.settings import get_settings

logger = logging.getLogger("multimcp_api.eval.worker")
POLL_SECONDS = float(os.environ.get("EVAL_POLL_SECONDS", "2"))
LOCK_SECONDS = int(os.environ.get("EVAL_LOCK_SECONDS", "300"))
BATCH_SIZE = int(os.environ.get("EVAL_BATCH_SIZE", "5"))


async def run_worker() -> None:
    settings = get_settings()
    if settings.storage_backend == "bigquery":
        raise SystemExit(
            "Eval worker requires STORAGE_BACKEND=postgres; use EVAL_BACKEND=inline with BigQuery"
        )
    repository = build_repository(settings)
    judge = OpenAIJudgeClient(
        model=settings.judge_model,
        api_key=settings.judge_api_key,
        base_url=settings.judge_base_url,
    )
    logger.info("eval worker started")
    while True:
        jobs = await repository.claim_eval_jobs(BATCH_SIZE, LOCK_SECONDS)
        if not jobs:
            await asyncio.sleep(POLL_SECONDS)
            continue
        for job in jobs:
            await run_eval_job(
                repository, judge, job.job_id, judge_model=settings.judge_model
            )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
