from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..assistant import service
from ..audit import registrar
from ..db import get_db
from ..models import Projeto, Usuario
from ..security import exige
from ..util import obter

router = APIRouter(prefix="/api", tags=["assistente"])


@router.get("/assistente/status")
def status(_: Usuario = Depends(exige("assistente.usar"))):
    return service.status()


@router.post("/projetos/{pid}/assistente")
def conversar(pid: int, d: dict, u: Usuario = Depends(exige("assistente.usar")), db: Session = Depends(get_db)):
    p = obter(db, Projeto, pid, "Projeto")
    hist = d.get("mensagens") or []
    r = service.responder(db, p, u, hist[-20:])
    registrar(db, u, "assistente", "projeto", pid, {"pergunta": (hist[-1]["content"] if hist else "")[:300], "ferramentas": r.get("ferramentas"), "modo": r.get("modo")})
    db.commit()
    return r
