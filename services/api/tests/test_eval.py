from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from multimcp_api.eval.judge import JudgeVerdict, OpenAIJudgeClient
from multimcp_api.eval.runner import run_eval_job
from multimcp_api.main import create_app
from multimcp_api.repositories.memory import MemoryEventRepository
from multimcp_api.settings import Settings


class FakeJudge:
    def __init__(self, verdict: JudgeVerdict | Exception):
        self._verdict = verdict
        self.calls = 0

    async def judge(self, *, query: str, contexts: list[str], answer: str) -> JudgeVerdict:
        self.calls += 1
        if isinstance(self._verdict, Exception):
            raise self._verdict
        return self._verdict


@pytest.fixture
def repo() -> MemoryEventRepository:
    return MemoryEventRepository()


@pytest.mark.asyncio
async def test_inline_evaluation_succeeds(repo: MemoryEventRepository) -> None:
    verdict = JudgeVerdict(
        context_relevance=0.8,
        hallucination_label="supported",
        rationale="grounded",
    )
    judge = FakeJudge(verdict)
    app = create_app(
        settings=Settings(
            ingest_token="test-token",
            eval_backend="inline",
            judge_model="gpt-4.1-mini",
        ),
        repository=repo,
    )
    app.state.judge_factory = lambda _settings: judge

    body = {
        "schema_version": "1.0",
        "rubric_version": "rag-judge-1.0",
        "query": "what is 2+2?",
        "contexts": ["2+2=4"],
        "answer": "4",
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/v1/evaluations",
            json=body,
            headers={"Authorization": "Bearer test-token"},
        )
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        status = await client.get(
            f"/api/v1/evaluations/{job_id}",
            headers={"Authorization": "Bearer test-token"},
        )

    assert status.status_code == 200
    payload = status.json()
    assert payload["status"] == "succeeded"
    assert payload["hallucination_label"] == "supported"
    assert judge.calls == 1


@pytest.mark.asyncio
async def test_runner_requeues_before_max_attempts(repo: MemoryEventRepository) -> None:
    from multimcp_api.domain.models import EvalJob

    job = EvalJob(
        rubric_version="rag-judge-1.0",
        query="q",
        contexts=["c"],
        answer="a",
    )
    await repo.enqueue_eval(job)
    await repo.start_eval(job.job_id, lock_seconds=30)
    await run_eval_job(repo, FakeJudge(RuntimeError("boom")), job.job_id)
    stored = await repo.get_eval(job.job_id)
    assert stored is not None
    assert stored.status == "queued"
    assert stored.attempt == 1


@pytest.mark.asyncio
async def test_runner_fails_after_three_attempts(repo: MemoryEventRepository) -> None:
    from multimcp_api.domain.models import EvalJob

    job = EvalJob(
        rubric_version="rag-judge-1.0",
        query="q",
        contexts=["c"],
        answer="a",
        attempt=2,
    )
    await repo.enqueue_eval(job)
    # start_eval bumps attempt to 3
    await repo.start_eval(job.job_id, lock_seconds=30)
    await run_eval_job(repo, FakeJudge(RuntimeError("boom")), job.job_id)
    stored = await repo.get_eval(job.job_id)
    assert stored is not None
    assert stored.status == "failed"
    assert stored.attempt == 3


def test_openai_judge_retries_invalid_json_once() -> None:
    class BoomClient:
        def __init__(self) -> None:
            self.calls = 0
            self.responses = SimpleNamespace(
                create=self.create,
            )

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(output_text="not-json")
            return SimpleNamespace(
                output_text='{"context_relevance":0.5,"hallucination_label":"partial","rationale":"mixed"}'
            )

    raw = BoomClient()
    # OpenAIJudgeClient expects .responses.create
    client = SimpleNamespace(responses=raw)
    judge = OpenAIJudgeClient(model="m", api_key="k", client=client)

    import asyncio

    verdict = asyncio.run(
        judge.judge(query="q", contexts=["c"], answer="a")
    )
    assert verdict.hallucination_label == "partial"
    assert raw.calls == 2
    # wrap_openai patches methods in place; metadata applied at wrap time.
