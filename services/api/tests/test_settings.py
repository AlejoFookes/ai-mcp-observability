import os

from multimcp_api.settings import Settings


def test_defaults_match_spec() -> None:
    # Pin storage_backend so a developer shell with STORAGE_BACKEND=memory
    # does not flake this assertion.
    settings = Settings(
        ingest_token="",
        storage_backend="postgres",
        eval_backend="postgres",
    )
    assert settings.storage_backend == "postgres"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.eval_backend == "postgres"
    assert settings.bq_dataset == "multimcp"
    assert settings.ingest_token == ""


def test_alembic_url_derived_from_database_url() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://u:p@localhost:5432/db",
        alembic_database_url=None,
    )
    assert settings.resolved_alembic_database_url == "postgresql+psycopg://u:p@localhost:5432/db"


def test_alembic_url_explicit_wins() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://u:p@localhost:5432/db",
        alembic_database_url="postgresql+psycopg://other/db",
    )
    assert settings.resolved_alembic_database_url == "postgresql+psycopg://other/db"


def test_memory_backend_builds_memory_repository() -> None:
    from multimcp_api.repositories.factory import build_repository
    from multimcp_api.repositories.memory import MemoryEventRepository

    settings = Settings(storage_backend="memory", ingest_token="x")
    repo = build_repository(settings)
    assert isinstance(repo, MemoryEventRepository)


def test_load_dotenv_fills_empty_environ(tmp_path, monkeypatch) -> None:
    from multimcp_api import settings as settings_mod

    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=\nOPENAI_API_KEY=gsk_test_from_dotenv\nINGEST_TOKEN=tok\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("INGEST_TOKEN", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.chdir(tmp_path)
    settings_mod._load_dotenv_into_environ()
    assert os.environ.get("OPENAI_API_KEY") == "gsk_test_from_dotenv"
    assert os.environ.get("INGEST_TOKEN") == "tok"
