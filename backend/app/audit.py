from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .models import Auditoria, Usuario


def registrar(db: Session, usuario: Usuario | None, acao: str, entidade: str, entidade_id: Any = None, detalhes: dict | None = None):
    db.add(Auditoria(
        usuario_id=usuario.id if usuario else None,
        usuario_nome=usuario.nome if usuario else None,
        acao=acao, entidade=entidade,
        entidade_id=str(entidade_id) if entidade_id is not None else None,
        detalhes=detalhes,
    ))
