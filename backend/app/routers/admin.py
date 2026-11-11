from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..engine import ENGINE_VERSION
from ..models import Auditoria, Calculo, Cliente, Projeto, Usuario, Versao
from ..security import exige
from ..util import to_dict

router = APIRouter(prefix="/api", tags=["administração"])


@router.get("/saude")
def saude(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    s = get_settings()
    return {"status": "ok", "versao": s.app_version, "ambiente": s.app_env, "git_sha": s.git_sha}


@router.get("/versao")
def versao_publica():
    s = get_settings()
    return {"versao": s.app_version, "ambiente": s.app_env, "git_sha": s.git_sha[:12], "versao_motor": ENGINE_VERSION}


@router.get("/admin/versao")
def versao(_: Usuario = Depends(exige("admin.ver")), db: Session = Depends(get_db)):
    s = get_settings()
    rev = None
    try:
        rev = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        db.rollback()
    return {"versao": s.app_version, "ambiente": s.app_env, "git_sha": s.git_sha, "data_build": s.build_date,
            "versao_motor": ENGINE_VERSION, "migracao_banco": rev, "banco": db.bind.dialect.name}


@router.get("/admin/versoes")
def historico_versoes(_: Usuario = Depends(exige("admin.ver")), db: Session = Depends(get_db)):
    return [to_dict(v) for v in db.scalars(select(Versao).order_by(Versao.id.desc()).limit(200)).all()]


@router.get("/admin/auditoria")
def auditoria(entidade: str | None = None, limite: int = 300, _: Usuario = Depends(exige("admin.ver")), db: Session = Depends(get_db)):
    q = select(Auditoria)
    if entidade:
        q = q.where(Auditoria.entidade == entidade)
    return [to_dict(a) for a in db.scalars(q.order_by(Auditoria.id.desc()).limit(min(limite, 2000))).all()]


@router.get("/painel")
def painel(u: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    contagem = dict(db.execute(select(Projeto.status, func.count(Projeto.id)).group_by(Projeto.status)).all())
    recentes = db.scalars(select(Projeto).order_by(Projeto.atualizado_em.desc()).limit(8)).all()
    return {
        "projetos_por_status": contagem,
        "total_clientes": db.scalar(select(func.count(Cliente.id))),
        "total_calculos": db.scalar(select(func.count(Calculo.id))),
        "recentes": [{"id": p.id, "codigo": p.codigo, "nome": p.nome, "status": p.status, "modulo": p.modulo,
                      "demonstrativo": p.demonstrativo, "atualizado_em": p.atualizado_em.isoformat()} for p in recentes],
    }
