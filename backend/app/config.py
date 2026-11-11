from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


def _versao_arquivo() -> str:
    for p in (BASE_DIR / "VERSION", BASE_DIR.parent / "VERSION"):
        if p.exists():
            return p.read_text().strip()
    return "0.0.0-dev"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "desenvolvimento"  # desenvolvimento | homologacao | producao
    app_version: str = _versao_arquivo()
    git_sha: str = "local"
    build_date: str = ""
    database_url: str = f"sqlite:///{BASE_DIR / 'dados' / 'app.db'}"
    secret_key: str = "troque-esta-chave-em-producao"
    token_horas: int = 12
    storage_dir: str = str(BASE_DIR / "dados" / "arquivos")
    max_upload_mb: int = 100
    frontend_dist: str = str(BASE_DIR.parent / "frontend" / "dist")
    admin_email: str = "admin@exemplo.com"
    admin_password: str = "admin123"
    admin_nome: str = "Administrador"
    seed_demo: bool = True
    cors_origins: str = "http://localhost:5173"
    anthropic_model: str = "claude-opus-5-5"
    assistente_habilitado: bool = True
    oda_converter_path: str = ""  # caminho do ODA File Converter para DWG (opcional)

    @field_validator("database_url")
    @classmethod
    def _driver_postgres(cls, v: str) -> str:
        """Provedores (ex.: Render) entregam postgres:// ou postgresql://; o driver usado é o psycopg 3."""
        for prefixo in ("postgres://", "postgresql://"):
            if v.startswith(prefixo):
                return "postgresql+psycopg://" + v[len(prefixo):]
        return v

    @field_validator("git_sha")
    @classmethod
    def _sha_render(cls, v: str) -> str:
        if v == "local":
            return os.environ.get("RENDER_GIT_COMMIT") or v
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
