from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..db import get_db
from ..models import Cliente, Projeto, Rede, Visita, Usuario
from ..security import exige
from .. import services as sv
from ..util import obter, to_dict

router = APIRouter(prefix="/api/visitas", tags=["visitas técnicas"])

MAPA_ENTRADAS = {"temperatura_c": "temperatura_c", "altitude_m": "altitude_m", "comprimento_m": "comprimento_m",
                 "largura_m": "largura_m", "pe_direito_m": "pe_direito_m", "ocupantes": "ocupantes"}


def visita_dict(v: Visita) -> dict:
    d = to_dict(v)
    d["faltantes"] = sv.faltantes_visita(v.dados or {})
    return d


@router.get("")
def listar(_: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    return [visita_dict(v) for v in db.scalars(select(Visita).order_by(Visita.id.desc())).all()]


@router.post("")
def criar(d: dict, u: Usuario = Depends(exige("visitas.editar")), db: Session = Depends(get_db)):
    if d.get("cliente_id"):
        obter(db, Cliente, d["cliente_id"], "Cliente")
    v = Visita(cliente_id=d.get("cliente_id"), projeto_id=d.get("projeto_id"), data=d.get("data"),
               responsavel_visita=d.get("responsavel_visita") or u.nome, dados=d.get("dados") or {}, criado_por=u.id)
    db.add(v)
    db.flush()
    registrar(db, u, "criar", "visita", v.id)
    db.commit()
    return visita_dict(v)


@router.get("/{vid}")
def obter_visita(vid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    return visita_dict(obter(db, Visita, vid, "Visita"))


@router.put("/{vid}")
def editar(vid: int, d: dict, u: Usuario = Depends(exige("visitas.editar")), db: Session = Depends(get_db)):
    v = obter(db, Visita, vid, "Visita")
    for k in ("cliente_id", "projeto_id", "data", "responsavel_visita"):
        if k in d:
            setattr(v, k, d[k])
    if "dados" in d:
        v.dados = d["dados"]
    registrar(db, u, "editar", "visita", v.id)
    db.commit()
    return visita_dict(v)


@router.post("/{vid}/criar-projeto")
def criar_projeto(vid: int, d: dict | None = None, u: Usuario = Depends(exige("projetos.editar")), db: Session = Depends(get_db)):
    """Cria projeto inicial com dados parciais. Todos os valores vindos da visita
    entram como 'nao_confirmado' até a confirmação do responsável técnico."""
    d = d or {}
    v = obter(db, Visita, vid, "Visita")
    dados = v.dados or {}
    modulo = d.get("modulo") or dados.get("tipo_sistema")
    if modulo not in sv.MODULOS:
        raise HTTPException(422, "Defina o tipo de sistema (poeira, fumos ou renovacao)")
    from .projetos import criar as criar_proj, projeto_dict
    p_d = criar_proj({"nome": d.get("nome") or f"{dados.get('atividade') or 'Projeto'} — visita {v.id}", "modulo": modulo,
                      "cliente_id": v.cliente_id, "descricao": dados.get("descricao_problema")}, u, db)
    p = db.get(Projeto, p_d["id"])
    campos = {c[0]: c for c in sv.campos_modulo(modulo)}
    ent = {}
    for k_vis, k_proj in MAPA_ENTRADAS.items():
        if dados.get(k_vis) not in (None, "") and k_proj in campos:
            ent[k_proj] = {"valor": dados[k_vis], "unidade": campos[k_proj][2], "rotulo": campos[k_proj][1],
                           "status": "nao_confirmado", "fonte": f"Visita técnica {v.id}"}
    p.entradas = ent
    p.riscos = {k: bool(val) for k, val in (dados.get("riscos") or {}).items()}
    # Captores sugeridos a partir dos pontos de emissão com posição
    nodes = []
    for i, pe in enumerate(dados.get("pontos_emissao") or [], 1):
        if isinstance(pe.get("x"), (int, float)) and isinstance(pe.get("y"), (int, float)):
            nodes.append({"id": f"C{i}", "type": "captor", "x": pe["x"], "y": pe["y"], "label": pe.get("nome") or f"C{i}",
                          "captor": {k: pe.get(k) for k in ("tipo", "processo", "distancia_m", "area_face_m2", "vazao_m3h", "entrada") if pe.get(k) is not None}})
    if nodes:
        r = db.scalars(select(Rede).where(Rede.projeto_id == p.id)).first()
        r.dados = {"nodes": nodes, "segments": []}
    amb = {}
    if dados.get("comprimento_m") and dados.get("largura_m"):
        L, W = float(dados["comprimento_m"]), float(dados["largura_m"])
        amb["contorno"] = [[0, 0], [L, 0], [L, W], [0, W]]
    amb["obstaculos"] = [{"pontos": m["pontos"], "nome": m.get("nome")} for m in (dados.get("maquinas") or []) if m.get("pontos")]
    amb["pilares"] = [{"pontos": m["pontos"]} for m in (dados.get("pilares") or []) if m.get("pontos")]
    p.ambiente = amb
    v.projeto_id = p.id
    registrar(db, u, "criar_de_visita", "projeto", p.id, {"visita_id": v.id})
    db.commit()
    return projeto_dict(db, p)
