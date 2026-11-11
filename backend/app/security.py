"""Autenticação (JWT) e autorização por perfil."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Usuario

PERFIS = {
    "administrador": "Administrador",
    "engenheiro": "Engenheiro responsável",
    "projetista": "Projetista",
    "tecnico_campo": "Técnico de campo",
    "orcamentista": "Orçamentista",
    "operador_testes": "Operador de testes",
}

# Permissões granulares
P = {
    "ver": "Visualizar projetos e cadastros",
    "clientes.editar": "Cadastrar/editar clientes",
    "visitas.editar": "Registrar visitas técnicas",
    "projetos.editar": "Criar/editar projetos, redes e plantas",
    "calculos.executar": "Executar cálculos",
    "projetos.aprovar": "Aprovação técnica de projetos",
    "fabricacao.liberar": "Liberar projeto para fabricação",
    "catalogo.editar": "Editar catálogo técnico (exaustores e componentes)",
    "custos.editar": "Editar preços e custos",
    "parametros.editar": "Propor/editar parâmetros técnicos",
    "parametros.aprovar": "Aprovar parâmetros técnicos",
    "orcamento.ver": "Ver custos e orçamentos",
    "exportar": "Exportar desenhos, memoriais e listas",
    "antigos.editar": "Gerenciar biblioteca de projetos anteriores",
    "assistente.usar": "Usar o assistente técnico",
    "usuarios.gerenciar": "Gerenciar usuários",
    "admin.ver": "Painel administrativo (versão, auditoria)",
}

PERMISSOES = {
    "administrador": set(P),
    "engenheiro": set(P) - {"usuarios.gerenciar"},
    "projetista": {"ver", "clientes.editar", "visitas.editar", "projetos.editar", "calculos.executar",
                   "parametros.editar", "orcamento.ver", "exportar", "antigos.editar", "assistente.usar"},
    "tecnico_campo": {"ver", "clientes.editar", "visitas.editar", "assistente.usar"},
    "orcamentista": {"ver", "orcamento.ver", "custos.editar", "exportar", "assistente.usar"},
    "operador_testes": {"ver", "clientes.editar", "visitas.editar", "projetos.editar", "calculos.executar",
                        "orcamento.ver", "exportar", "antigos.editar", "assistente.usar"},
}

bearer = HTTPBearer(auto_error=False)


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode()


def verificar_senha(senha: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), h.encode())
    except ValueError:
        return False


def criar_token(usuario: Usuario) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(hours=s.token_horas)
    return jwt.encode({"sub": str(usuario.id), "perfil": usuario.perfil, "exp": exp}, s.secret_key, algorithm="HS256")


def usuario_atual(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> Usuario:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado")
    try:
        dados = jwt.decode(cred.credentials, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada")
    u = db.get(Usuario, int(dados["sub"]))
    if not u or not u.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário inativo")
    return u


def permissoes(u: Usuario) -> set[str]:
    return PERMISSOES.get(u.perfil, set())


def tem(u: Usuario, perm: str) -> bool:
    return perm in permissoes(u)


def exige(perm: str):
    def dep(u: Usuario = Depends(usuario_atual)) -> Usuario:
        if not tem(u, perm):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Seu perfil não tem permissão: {P.get(perm, perm)}")
        return u
    return dep
