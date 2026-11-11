from app.config import Settings


def test_url_postgres_de_provedor_usa_psycopg(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    assert Settings().database_url == "postgresql+psycopg://u:p@host:5432/db"
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host/db")
    assert Settings().database_url == "postgresql+psycopg://u:p@host/db"
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@host/db")
    assert Settings().database_url == "postgresql+psycopg://u:p@host/db"


def test_commit_do_render(monkeypatch):
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc1234")
    assert Settings().git_sha == "abc1234"
    monkeypatch.setenv("GIT_SHA", "def5678")
    assert Settings().git_sha == "def5678"
