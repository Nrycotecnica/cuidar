import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp(prefix="vent_teste_")
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/teste.db"
os.environ["STORAGE_DIR"] = f"{_tmp}/arquivos"
os.environ["FRONTEND_DIST"] = f"{_tmp}/sem_frontend"
os.environ["SEED_DEMO"] = "true"
os.environ["ADMIN_EMAIL"] = "admin@teste.com"
os.environ["ADMIN_PASSWORD"] = "senha-admin-123"
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


def login(client, email, senha):
    r = client.post("/api/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture(scope="session")
def admin(client):
    return login(client, "admin@teste.com", "senha-admin-123")


@pytest.fixture(scope="session")
def usuarios(client, admin):
    """Cria um usuário de cada perfil e devolve os cabeçalhos de autenticação."""
    out = {"administrador": admin}
    for perfil in ("engenheiro", "projetista", "tecnico_campo", "orcamentista", "operador_testes"):
        email = f"{perfil}@teste.com"
        r = client.post("/api/usuarios", headers=admin, json={"email": email, "nome": perfil.title(), "perfil": perfil,
                                                              "senha": "senha-1234", "registro_profissional": "CREA-TESTE" if perfil == "engenheiro" else None})
        assert r.status_code == 200, r.text
        out[perfil] = login(client, email, "senha-1234")
    return out
