from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..db import get_db
from ..models import Cliente, Projeto, Usuario
from ..security import exige
from ..util import aplicar, obter, to_dict

router = APIRouter(prefix="/api/clientes", tags=["clientes"])
CAMPOS = {"nome", "industria", "cnpj", "endereco", "contato_nome", "contato_telefone", "contato_email", "atividade", "observacoes"}


@router.get("")
def listar(_: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    return [to_dict(c) for c in db.scalars(select(Cliente).order_by(Cliente.nome)).all()]


@router.post("")
def criar(d: dict, u: Usuario = Depends(exige("clientes.editar")), db: Session = Depends(get_db)):
    if not (d.get("nome") or "").strip():
        raise HTTPException(422, "Nome do cliente é obrigatório")
    c = Cliente(**{k: v for k, v in d.items() if k in CAMPOS})
    db.add(c)
    db.flush()
    registrar(db, u, "criar", "cliente", c.id, {"nome": c.nome})
    db.commit()
    return to_dict(c)


@router.get("/{cid}")
def obter_cliente(cid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    return to_dict(obter(db, Cliente, cid, "Cliente"))


@router.put("/{cid}")
def editar(cid: int, d: dict, u: Usuario = Depends(exige("clientes.editar")), db: Session = Depends(get_db)):
    c = obter(db, Cliente, cid, "Cliente")
    alt = aplicar(c, d, CAMPOS)
    registrar(db, u, "editar", "cliente", c.id, alt)
    db.commit()
    return to_dict(c)


@router.delete("/{cid}")
def excluir(cid: int, u: Usuario = Depends(exige("clientes.editar")), db: Session = Depends(get_db)):
    c = obter(db, Cliente, cid, "Cliente")
    if db.scalars(select(Projeto).where(Projeto.cliente_id == cid)).first():
        raise HTTPException(409, "Cliente possui projetos vinculados")
    registrar(db, u, "excluir", "cliente", c.id, {"nome": c.nome})
    db.delete(c)
    db.commit()
    return {"ok": True}
