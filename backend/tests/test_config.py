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


def test_versao_vazia_usa_arquivo(monkeypatch):
    from app.config import _versao_arquivo
    monkeypatch.setenv("APP_VERSION", "")
    assert Settings().app_version == _versao_arquivo() != ""
    monkeypatch.setenv("APP_VERSION", "9.9.9")
    assert Settings().app_version == "9.9.9"
