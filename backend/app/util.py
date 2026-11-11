from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session


def to_dict(obj, excluir: tuple[str, ...] = ()) -> dict[str, Any]:
    out = {}
    for c in obj.__table__.columns:
        if c.name in excluir:
            continue
        v = getattr(obj, c.name)
        if isinstance(v, datetime):
            v = v.isoformat()
        out[c.name] = v
    return out


def obter(db: Session, modelo, id_: int, nome: str = "Registro"):
    o = db.get(modelo, id_)
    if o is None:
        raise HTTPException(404, f"{nome} não encontrado")
    return o


def aplicar(obj, dados: dict, permitidos: set[str]):
    alterados = {}
    for k, v in dados.items():
        if k in permitidos and getattr(obj, k) != v:
            alterados[k] = {"de": _ser(getattr(obj, k)), "para": _ser(v)}
            setattr(obj, k, v)
    return alterados


def _ser(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (dict, list)):
        return "(estrutura)"
    return v
