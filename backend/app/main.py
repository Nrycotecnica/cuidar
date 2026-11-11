from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import SessionLocal
from .routers import admin, antigos, arquivos, assistente, auth, calculos, catalogo, clientes, projetos, visitas
from .seed import inicializar


CHAVE_PADRAO = "troque-esta-chave-em-producao"


def verificar_configuracao():
    s = get_settings()
    if s.app_env != "desenvolvimento":
        if s.secret_key == CHAVE_PADRAO or len(s.secret_key) < 32:
            raise RuntimeError("SECRET_KEY ausente ou fraca: defina uma chave aleatória com pelo menos 32 caracteres.")
        if s.admin_password == "admin123":
            raise RuntimeError("ADMIN_PASSWORD padrão não é permitida fora do ambiente de desenvolvimento.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    verificar_configuracao()
    with SessionLocal() as db:
        inicializar(db)
    yield


def criar_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Ventilação Industrial — Engenharia", version=s.app_version, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
                       allow_methods=["*"], allow_headers=["*"])
    for r in (auth, clientes, projetos, visitas, arquivos, catalogo, calculos, antigos, admin, assistente):
        app.include_router(r.router)

    dist = Path(s.frontend_dist)
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{caminho:path}", include_in_schema=False)
        def spa(caminho: str):
            if caminho.startswith("api/"):
                from fastapi import HTTPException
                raise HTTPException(404, "Rota inexistente")
            alvo = dist / caminho
            if caminho and alvo.is_file() and dist.resolve() in alvo.resolve().parents:
                return FileResponse(alvo)
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})
    return app


app = criar_app()
