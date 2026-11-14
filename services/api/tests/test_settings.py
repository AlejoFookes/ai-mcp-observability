from multimcp_api.settings import Settings


def test_defaults_match_spec() -> None:
    settings = Settings(ingest_token="")
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
