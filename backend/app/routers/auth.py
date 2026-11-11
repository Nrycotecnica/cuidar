from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..db import get_db
from ..models import Usuario
from ..security import P, PERFIS, criar_token, exige, hash_senha, permissoes, usuario_atual, verificar_senha
from ..util import aplicar, obter, to_dict

router = APIRouter(prefix="/api", tags=["autenticação"])


class Login(BaseModel):
    email: str
    senha: str


def usuario_publico(u: Usuario) -> dict:
    d = to_dict(u, excluir=("senha_hash",))
    d["perfil_nome"] = PERFIS.get(u.perfil, u.perfil)
    d["permissoes"] = sorted(permissoes(u))
    return d


@router.post("/auth/login")
def login(dados: Login, db: Session = Depends(get_db)):
    u = db.scalars(select(Usuario).where(Usuario.email == dados.email.strip().lower())).first()
    if not u or not u.ativo or not verificar_senha(dados.senha, u.senha_hash):
        raise HTTPException(401, "E-mail ou senha inválidos")
    registrar(db, u, "login", "usuario", u.id)
    db.commit()
    return {"token": criar_token(u), "usuario": usuario_publico(u)}


@router.get("/auth/eu")
def eu(u: Usuario = Depends(usuario_atual)):
    return usuario_publico(u)


class TrocaSenha(BaseModel):
    senha_atual: str
    nova_senha: str


@router.post("/auth/senha")
def trocar_senha(d: TrocaSenha, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    if not verificar_senha(d.senha_atual, u.senha_hash):
        raise HTTPException(400, "Senha atual incorreta")
    if len(d.nova_senha) < 8:
        raise HTTPException(400, "A nova senha deve ter pelo menos 8 caracteres")
    u.senha_hash = hash_senha(d.nova_senha)
    registrar(db, u, "trocar_senha", "usuario", u.id)
    db.commit()
    return {"ok": True}


@router.get("/perfis")
def perfis(_: Usuario = Depends(usuario_atual)):
    from ..security import PERMISSOES
    return {"perfis": PERFIS, "permissoes": P, "matriz": {k: sorted(v) for k, v in PERMISSOES.items()}}


class NovoUsuario(BaseModel):
    email: str
    nome: str
    perfil: str
    senha: str
    registro_profissional: str | None = None


@router.get("/usuarios")
def listar_usuarios(_: Usuario = Depends(exige("usuarios.gerenciar")), db: Session = Depends(get_db)):
    return [usuario_publico(u) for u in db.scalars(select(Usuario).order_by(Usuario.nome)).all()]


@router.post("/usuarios")
def criar_usuario(d: NovoUsuario, adm: Usuario = Depends(exige("usuarios.gerenciar")), db: Session = Depends(get_db)):
    if d.perfil not in PERFIS:
        raise HTTPException(422, "Perfil inválido")
    email = d.email.strip().lower()
    if db.scalars(select(Usuario).where(Usuario.email == email)).first():
        raise HTTPException(409, "E-mail já cadastrado")
    if len(d.senha) < 8:
        raise HTTPException(422, "A senha deve ter pelo menos 8 caracteres")
    u = Usuario(email=email, nome=d.nome, perfil=d.perfil, senha_hash=hash_senha(d.senha), registro_profissional=d.registro_profissional)
    db.add(u)
    db.flush()
    registrar(db, adm, "criar", "usuario", u.id, {"email": email, "perfil": d.perfil})
    db.commit()
    return usuario_publico(u)


@router.put("/usuarios/{uid}")
def editar_usuario(uid: int, d: dict, adm: Usuario = Depends(exige("usuarios.gerenciar")), db: Session = Depends(get_db)):
    u = obter(db, Usuario, uid, "Usuário")
    if "perfil" in d and d["perfil"] not in PERFIS:
        raise HTTPException(422, "Perfil inválido")
    alt = aplicar(u, d, {"nome", "perfil", "ativo", "registro_profissional"})
    if d.get("senha"):
        if len(d["senha"]) < 8:
            raise HTTPException(422, "A senha deve ter pelo menos 8 caracteres")
        u.senha_hash = hash_senha(d["senha"])
        alt["senha"] = "redefinida"
    registrar(db, adm, "editar", "usuario", u.id, alt)
    db.commit()
    return usuario_publico(u)
